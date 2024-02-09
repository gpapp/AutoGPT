from forge.sdk.forge_log import ForgeLogger
from forge.sdk.prompting import PromptEngine
from ..llm import chat_completion_request
from .registry import ability
import json

logger = ForgeLogger(__name__)

@ability(
    name="process_data",
    description="Process data based on a specified transformation description, make sure to pass a very detailed description of the desired transformation. You can also pass multiple transformation commands. You must give examples of the desired outcome in the description.",
    parameters=[
        {
            "name": "transformation_description",
            "description": "Detailed Description of the transformation to be applied",
            "type": "string",
            "required": True,
        },
        {
            "name": "input",
            "description": "The data to be transformed",
            "type": "string",
            "required": True,
        }
    ],
    output_type="string",
)
async def process_data(agent, task_id: str, transformation_description: str, input: str) -> str:
    # Determine the type of input_data
    if isinstance(input, bytes):
        input_str = input.decode('utf-8')
    elif isinstance(input, dict):
        input_str = json.dumps(input)
    else:
        input_str = str(input)

    prompt_engine = PromptEngine(agent.MODEL_NAME)
    
    # Check input length for direct transformation
    if len(input_str) < 4000:
        try:
            args={"description":transformation_description,"input":input_str}
            ability_prompt = prompt_engine.load_prompt("ability-direct-transformation", **args)
            kwargs = prompt_engine.get_model_parameters("model-params")
            kwargs.update(prompt_engine.get_model_parameters("ability-direct-transformation"))
            messages = [{"role": "system", "content": ability_prompt}]
            transformed_data = await execute_request(agent.MODEL_NAME,messages,**kwargs)
            return transformed_data
        except Exception as direct_e:
            direct_error_message = str(direct_e)
            logger.warning(f"Direct transformation error: {direct_error_message}")
            return json.dumps({"error": direct_error_message})

    # If input length >= 4000, continue with the current logic
    max_attempts = 2
    errors=[]
    kwargs = prompt_engine.get_model_parameters("model-params")
    kwargs.update(prompt_engine.get_model_parameters("ability-transformation-function"))
    ability_prompt = prompt_engine.load_prompt("ability-transformation-function", {"description":transformation_description,"attempt":attempt,"errors":errors})
    messages=[{"role": "system", "content": ability_prompt}]
    for attempt in range(max_attempts):
        try:
            transformation_function_code = await execute_request(agent.MODEL_NAME,messages,**kwargs)
            
            exec_globals = {}
            exec(transformation_function_code, {}, exec_globals)
            transformation_function = exec_globals['transformation_function']
            
            input_obj = json.loads(input_str)
            transformed_data_obj = transformation_function(input_obj)
            
            transformed_data = json.dumps(transformed_data_obj)
            return transformed_data

        except Exception as e:
            error_message = str(e)
            messages.append({
                "role": "user",
                "content": f"Previous error: {error_message} (Attempt {attempt + 1})"
            })
            messages.append({
                "role": "assistant",
                "content": transformation_function_code
            })
            errors.append(error_message)
            logger.warning(f"Attempt {attempt + 1}: Error processing data: {error_message}")

            # On the last attempt, directly ask the model for the transformation result
            if attempt == max_attempts - 1:
                try:
                    args={"description":transformation_description,"input":input_str}
                    ability_prompt = prompt_engine.load_prompt("ability-direct-transformation", **args)
                    kwargs = prompt_engine.get_model_parameters("model-params")
                    kwargs.update(prompt_engine.get_model_parameters("ability-direct-transformation"))
                    messages=[{"role": "system", "content": ability_prompt}]
                    transformed_data = await execute_request(agent.MODEL_NAME,messages,**kwargs)
                    return transformed_data
                except Exception as final_e:
                    final_error_message = str(final_e)
                    logger.warning(f"Final attempt: Error processing data: {final_error_message}")
                    return json.dumps({"error": final_error_message})


async def execute_request(model, messages, **kwargs) -> str:    
    response = await chat_completion_request(model,messages,**kwargs)    
    transformed_data = response["choices"][0]["message"]["content"].strip()
    return transformed_data
