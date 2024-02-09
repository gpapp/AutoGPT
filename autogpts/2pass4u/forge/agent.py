import os
import ast
import json
import asyncio
import pprint
import re

from forge.abilities import AbilityRegister
from forge.sdk import (
    Agent,
    AgentDB,
    Step,
    StepRequestBody,
    Workspace,
    ForgeLogger,
    Task,
    TaskRequestBody,
    PromptEngine,
    chat_completion_request,
)

LOG = ForgeLogger(__name__)

from datetime import datetime

class JSONEncoderWithBytes(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, bytes):
            return obj.decode('utf-8')
        # Add support for encoding datetime.datetime (or Timestamp) objects
        if isinstance(obj, datetime):
            return obj.isoformat()  # Convert to ISO formatted string
        return super().default(obj)
    
class ForgeAgent(Agent):
    MODEL_NAME = os.environ['MODEL_NAME']
    TWO_PASS = False
    RETRY_COUNT = 3
    RETRY_WAIT_SECONDS = 5  # wait for 5 seconds before retrying

    def __init__(self, database: AgentDB, workspace: Workspace):
        super().__init__(database, workspace)

        self.messages = [] 
        self.abilities = AbilityRegister(self)

    async def create_task(self, task_request: TaskRequestBody) -> Task:
        task = await super().create_task(task_request)
        LOG.info(
            f"📦 Task created: {task.task_id} input: {task.input[:40]}{'...' if len(task.input) > 40 else ''}"
        )
        return task
    
    async def execute_step(self, task_id: str, step_request: StepRequestBody) -> Step:
        task = await self.db.get_task(task_id)
        step = await self.db.create_step(
            task_id=task_id, input=step_request, additional_input=step_request.additional_input, is_last=False
        )

        current_files = self.workspace.list(task_id, ".")
        prompt_engine = PromptEngine(self.MODEL_NAME)
        if len(self.messages) < 2:
            system_kwargs = {
                "abilities": self.abilities.list_abilities_for_prompt(),
                "current_files": current_files
            }
            task_kwargs = {"task": task.input}
            
            system_prompt = prompt_engine.load_prompt("system-format", **system_kwargs)
            self.messages = [{"role": "system", "content": system_prompt}]
            task_prompt = prompt_engine.load_prompt("task-step", **task_kwargs)
            self.messages.append({"role": "user", "content": task_prompt})

        system_llm_kwargs = prompt_engine.get_model_parameters("system-format")

        if self.TWO_PASS:
            secpass_kwargs={
                "abilities": self.abilities.list_abilities_for_prompt(),
                "current_files": current_files,
                "task": task.input} 
            secpass_system_prompt = prompt_engine.load_prompt("second-pass-system", **secpass_kwargs)
            secpass_system_llm_kwargs = prompt_engine.get_model_parameters("second-pass-system")

        LOG.debug(f"\n\n\nSending the following messages to the model: {pprint.pformat(self.messages)}")

        for retry_attempt in range(self.RETRY_COUNT):
            try:
                # Chat completion request                
                chat_completion_kwargs = {
                    "messages": self.messages,                    
                    "model": self.MODEL_NAME
                }
                chat_completion_kwargs.update(system_llm_kwargs)
                chat_response = await chat_completion_request(**chat_completion_kwargs)            

                answer_content = chat_response["choices"][0]["message"]["content"]
                if self.TWO_PASS:
                    secpass_kwargs={"task": task.input, "answer": answer_content} 
                    secpass_messages = [{"role": "system", "content": secpass_system_prompt}]
                    secpass_user_prompt = prompt_engine.load_prompt("second-pass-user", **secpass_kwargs)
                    secpass_messages.append({"role": "user", "content": secpass_user_prompt})
                    secpass_chat_completion_kwargs = {
                        "messages" : secpass_messages,
                        "model" : self.MODEL_NAME
                    }
                    secpass_chat_completion_kwargs.update(secpass_system_llm_kwargs)
                    LOG.debug(f"\n\n\nSending the following messages to the model: {pprint.pformat(secpass_messages)}")
                    chat_response = await chat_completion_request(**secpass_chat_completion_kwargs)                    
                    answer_content = chat_response["choices"][0]["message"]["content"]


                # Check if the content is already a dictionary (JSON-like structure)
                if isinstance(answer_content, dict):
                    answer = answer_content
                else:
                    try:
                        # If answer_content is bytes, decode it
                        if isinstance(answer_content, bytes):
                            answer_content = answer_content.decode('utf-8')
                        
                        # Attempt to parse the content as JSON
                        answer = extract_dict_from_response(answer_content)
                        LOG.debug(f"\n\n\nanswer: {pprint.pformat(answer)}")

                    except json.JSONDecodeError as e:
                        LOG.error(f"Unable to decode chat response: {chat_response}")
                        answer = None

                # Ability Sequence Execution
                ability_sequence = answer.get("abilities_sequence")
                last_output = False
                previous_outputs = {}

                for ability_item in ability_sequence:
                    ability = ability_item.get("ability", {})
                    LOG.debug("\n\nin the sequence %s", ability)

                    if "name" in ability and "args" in ability:
                        for (key,value) in previous_outputs:
                            for dk in ability["args"]:
                                ability["args"][dk]=str.replace(ability["args"][dk],f"{{key}}",value)

                        output = await self.abilities.run_ability(
                            task_id, ability["name"], **ability["args"]
                        )

                        LOG.debug("\n\nGot Output for %s : %s", ability["name"], output)

                        if isinstance(output, bytes):
                            output_str = output.decode('utf-8')
                        else:
                            output_str = output
                        if ability["name"] == "finish" or "File has been written successfully" in output_str:
                            step.is_last = True
                            step.status = "completed"
                        if "output" in ability:
                            previous_outputs[ability["output"]] = output
                        last_output=output

                step.output = answer.get("speak","")
                if last_output and isinstance(last_output, str):
                    answer["final_output"] = last_output

                # If everything is successful, break out of the retry loop
                LOG.info("\n\aanswer final %s", answer)
                break
            

            except Exception as e:
                if retry_attempt < self.RETRY_COUNT - 1:
                    LOG.warning(f"Error occurred in attempt {retry_attempt + 1}. {str(e)}")
                    await asyncio.sleep(self.RETRY_WAIT_SECONDS)
                else:
                    LOG.error(f"Error occurred in the final attempt {retry_attempt + 1}. Giving up.")
                    raise

        stringified_answer = json.dumps(answer, cls=JSONEncoderWithBytes)
        self.messages.append({"role": "assistant", "content": stringified_answer})

        if len(self.messages) >= 4:
            step.is_last = True

        return step

def extract_dict_from_response(response_content: str) -> dict[str, any]:
    # Sometimes the response includes the JSON in a code block with ```
    pattern = r"```([\s\S]*?)```"
    match = re.search(pattern, response_content)

    if match:
        response_content = match.group(1).strip()
        # Remove language names in code blocks
        response_content = response_content.lstrip("json")
    else:
        # The string may contain JSON.
        json_pattern = r"{[\s\S]*}"
        match = re.search(json_pattern, response_content)

        if match:
            response_content = match.group()

    # Response content comes from OpenAI as a Python `str(content_dict)`.
    # `literal_eval` does the reverse of `str(dict)`.
    try:
        result = ast.literal_eval(response_content)
    except Exception as e:
        result = json.loads(response_content)

    if not isinstance(result, dict):
        raise ValueError(
            f"Response '''{response_content}''' evaluated to "
            f"non-dict value {repr(result)}"
        )
    return result
