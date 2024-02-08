from forge.sdk.forge_log import ForgeLogger
from forge.sdk.prompting import PromptEngine

from ..llm import chat_completion_request
from .registry import ability
import json

logger = ForgeLogger(__name__)

"""
@ability(
    name="plan",
    description="Use this action to break down an larger task into smaller components.",
    parameters=[
        {
            "name": "to_think",
            "description": "The topic to think about",
            "type": "string",
            "required": True,
        },
    ],
    output_type="string",
)
 async def plan_ahead(agent, task_id: str, to_think:str, context:dict) -> str:
        
    # Check input length for direct transformation
    try:
        prompt_engine = PromptEngine(agent.MODEL_NAME)
        system_kwargs = {
            "abilities": agent.abilities.list_abilities_for_prompt()
        }
        task_kwargs = {"task": agent.ta}
        system_prompt = prompt_engine.load_prompt("system-format", **system_kwargs)
        messages = [{"role": "system", "content": system_prompt}]
        task_prompt = prompt_engine.load_prompt("task-step", **task_kwargs)
        messages.append({"role": "user", "content": task_prompt})
        for retry_attempt in range(agent.RETRY_COUNT):
            try:
                # Chat completion request                
                chat_completion_kwargs = {
                    "messages": agent.messages,                    
                    "model": agent.MODEL_NAME
                }
                chat_completion_kwargs.update(system_llm_kwargs)
                chat_response = await chat_completion_request(**chat_completion_kwargs)            

                answer_content = chat_response["choices"][0]["message"]["content"]
                return answer_content
            except Exception as ex:
                logger.warning(f"Thinking error: {direct_error_message}")
                pass
    except Exception as direct_e:
        direct_error_message = str(direct_e)
        logger.warning(f"Thinking error: {direct_error_message}")
        return json.dumps({"error": direct_error_message})
"""
 