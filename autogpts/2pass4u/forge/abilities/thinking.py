from forge.sdk.forge_log import ForgeLogger
from forge.sdk.prompting import PromptEngine

from ..llm import chat_completion_request
from .registry import ability
import json

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
        context=""
        try:
            context=agent.messages[1]["content"]
        except:
            context=""
        propmt_args={"task":to_plan,"context":context,"abilities":agent.abilities.list_abilities_for_prompt()}
        ability_prompt = prompt_engine.load_prompt("ability-plan-ahead", **propmt_args)
        kwargs = prompt_engine.get_model_parameters("ability-plan-ahead")
        messages=[{"role": "system", "content": ability_prompt}]
        for retry_attempt in range(agent.RETRY_COUNT):
            chat_response = await chat_completion_request(agent.MODEL_NAME, messages, **kwargs)            

            answer_content = chat_response["choices"][0]["message"]["content"]

        return answer_content
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
        kwargs = prompt_engine.get_model_parameters("ability-think")
        messages=[{"role": "system", "content": ability_prompt}]
        for retry_attempt in range(agent.RETRY_COUNT):
            chat_response = await chat_completion_request(agent.MODEL_NAME,messages,**kwargs)            

            answer_content = chat_response["choices"][0]["message"]["content"]

        return answer_content
    except Exception as direct_e:
        direct_error_message = str(direct_e)
        logger.warning(f"Thinking error: {direct_error_message}")
        return json.dumps({"error": direct_error_message})
