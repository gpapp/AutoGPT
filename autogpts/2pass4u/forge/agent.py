import os
import json

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
        await self.abilities.run_ability(task_id,"plan", {"input",task.input})
        return step

