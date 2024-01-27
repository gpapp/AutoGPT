# 2pass4u

This is an attempt to write a two pass agent, that uses local llm.

The LLM tested with this is text-generation-webui.

Make sure to load a model (e.g.TheBloke_Mistral-7B-Instruct-v0.2-GPTQ) and set the corresponding instruction template for the model in llm.py. Otherwise you may end up without system prompts.