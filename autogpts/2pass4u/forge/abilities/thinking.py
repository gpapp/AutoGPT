import ast
import asyncio
import pprint
import re
import json

from forge.sdk.forge_log import ForgeLogger
from forge.sdk.prompting import PromptEngine
from forge.sdk import StepRequestBody
from ..llm import chat_completion_request
from .registry import ability

logger = ForgeLogger(__name__)

@ability(
    name="plan",
    description="Use this action to break down an larger task into smaller components.",
    parameters=[
        {
            "name": "to_plan",
            "description": "The task to break down into components",
            "type": "string",
            "required": True,
        },
    ],
    output_type="string",
)
async def plan_ahead(agent, task_id: str, to_plan:str) -> str:
        
    # Check input length for direct transformation
    prompt_engine = PromptEngine(agent.MODEL_NAME)
    try:
        current_files = agent.workspace.list(task_id, ".")

        context=""
        propmt_args={"task":to_plan,
                     "context":context,
                     "abilities":agent.abilities.list_abilities_for_prompt(),
                     "files":current_files}
        kwargs = prompt_engine.get_model_parameters("model-params")
        kwargs.update(prompt_engine.get_model_parameters("ability-plan-ahead"))
        messages=[
            {"role": "system", "content": prompt_engine.load_prompt("ability-plan-ahead-system", **propmt_args)},
            {"role": "system", "content": prompt_engine.load_prompt("ability-plan-ahead-user", **propmt_args)},
            ]
        for retry_attempt in range(agent.RETRY_COUNT):
            chat_response = await chat_completion_request(agent.MODEL_NAME, messages, **kwargs)
            answer_content = chat_response["choices"][0]["message"]["content"]

            propmt_args={ "task":to_plan,
                          "input":answer_content,
                          "context":context,
                          "abilities":agent.abilities.list_abilities_for_prompt()
                        }
            formatter_messages=[
                {"role": "system", "content": prompt_engine.load_prompt("ability-formatter-system", **propmt_args)},
                {"role": "user", "content": prompt_engine.load_prompt("ability-formatter-user", **propmt_args)},
                ]

            formatter_kwargs = prompt_engine.get_model_parameters("model-params")
            formatter_kwargs.update(prompt_engine.get_model_parameters("ability-formatter"))

            for retry_attempt in range(agent.RETRY_COUNT):
                try:
                    formatter_response = await chat_completion_request(agent.MODEL_NAME, formatter_messages, **formatter_kwargs)
                    answer_content = formatter_response["choices"][0]["message"]["content"]
                    answer = extract_dict_from_response(answer_content)
                    ability_sequence = answer.get("abilities_sequence")
                    break
                except Exception as direct_e:
                    direct_error_message = str(direct_e)
                    logger.warning(f"Thinking error, cannot format output to JSON: {direct_error_message}")
                    if (retry_attempt==agent.RETRY_COUNT-1):
                        raise Exception("Cannot format thinking")

            previous_outputs = {}
            for ability_item in ability_sequence:
                ability = ability_item.get("ability", {})
                logger.debug("\n\nin the sequence %s", ability)
                if "name" in ability and "args" in ability:
                    
                    for key in previous_outputs:
                        for dk in ability["args"]:
                            ability["args"][dk]=str.replace(ability["args"][dk],key,previous_outputs[key])
                    
                    logger.debug("\n\nGot Output for %s : %s", ability["name"], ability)
                    steprequest = StepRequestBody(name=ability["name"],input=ability["name"],additional_input=ability)
                    if ability["name"] == "finish":
                        step = await agent.db.create_step(
                            task_id=task_id, input=steprequest, additional_input=ability, is_last=True
                        )
                    else:
                        step = await agent.db.create_step(
                            task_id=task_id, input=steprequest, additional_input=ability, is_last=False
                        )
                    for retry_attempt in range(agent.RETRY_COUNT):
                        try:
                            output = await agent.abilities.run_ability(
                                task_id, ability["name"], **ability["args"]
                            )
                            if isinstance(output, bytes):
                                output_str = output.decode('utf-8')
                            else:
                                output_str = output
                            if ability.get("output"):
                                previous_outputs[ability["output"]] = output                    
                            logger.debug("\n\nGot Output for %s : %s", ability["name"], output)                          
                            if isinstance(output, bytes):
                                output_str = output.decode('utf-8')
                            else:
                                output_str = output
                            await agent.db.update_step(task_id,step.step_id, status="Completed", output=output_str)
                            break
                        except Exception as direct_e:
                            direct_error_message = str(direct_e)
                            logger.warning(f"Thinking error: {direct_error_message}")
                            if (retry_attempt==agent.RETRY_COUNT-1):
                                await agent.db.update_step(task_id,step.step_id, status="Error", output=output_str)
                                raise Exception("Cannot format thinking")

            return answer
    except Exception as direct_e:
        direct_error_message = str(direct_e)
        logger.warning(f"Thinking error: {direct_error_message}")
        return json.dumps({"error": direct_error_message})

@ability(
    name="think",
    description="Use this action to think about a subject before planing the next steps."
                "The thinker does not know anything about the task, provide a detailed context for it to use.",
    parameters=[
        {
            "name": "to_think",
            "description": "The topic to think about",
            "type": "string",
            "required": True,
        },
        {
            "name": "context",
            "description": "Provide a context for the thinking.",
            "type": "string",
            "required": True,
        },
    ],
    output_type="string",
)
async def think(agent, task_id: str, to_think:str, context:str) -> str:
        
    # Check input length for direct transformation
    prompt_engine = PromptEngine(agent.MODEL_NAME)
    try:
        propmt_args={"task":to_think,"context":context}
        ability_prompt = prompt_engine.load_prompt("ability-think", **propmt_args)
        kwargs = prompt_engine.get_model_parameters("model-params")
        kwargs.update(prompt_engine.get_model_parameters("ability-think"))        
        messages=[{"role": "system", "content": ability_prompt}]
        for retry_attempt in range(agent.RETRY_COUNT):
            chat_response = await chat_completion_request(agent.MODEL_NAME,messages,**kwargs)            

            answer_content = chat_response["choices"][0]["message"]["content"]
            return answer_content
    except Exception as direct_e:
        direct_error_message = str(direct_e)
        logger.warning(f"Thinking error: {direct_error_message}")
        return json.dumps({"error": direct_error_message})

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


"""
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

        system_llm_kwargs = prompt_engine.get_model_parameters("model-params")
        system_llm_kwargs.update(prompt_engine.get_model_parameters("system-format"))

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
                        for key in previous_outputs:
                            for dk in ability["args"]:
                                ability["args"][dk]=str.replace(ability["args"][dk],key,previous_outputs[key])

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
                        if ability.get("output"):
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


"""