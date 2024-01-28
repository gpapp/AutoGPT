# 2pass4u

This is an attempt to write an autonomous agent, that uses local llm.

You will have to provide a suitably strong modell to run inference on. I found 13B models barely scratching the surface.

The model to be used is set in agent.py, find MODEL_NAME= in ForgeAgent class.
You'll need to use litellm's method of prefixing the modell name with connection type. So far petals and oobabooga were tested, with limited success.

The corresponding templates are loaded from the prompts directory.
Extra model parameters can be passed by adding them to system-format.json for the particular templates.

## text-generation-webui
The LLM tested with this is text-generation-webui.

Make sure to load a model (e.g.TheBloke_Mistral-7B-Instruct-v0.2-GPTQ) and set the corresponding instruction template for the model in llm.py. Otherwise you may end up without system prompts.

## PETALS
You can run your own petals server in a wsl2 environment
as described [here](https://github.com/petals-infra/chat.petals.dev)

Once your WSL2 is already running the server, don't forget to expose the endpoint to your machine, so the script can connect to it.

```
netsh interface portproxy add v4tov4 listenport=5000 listenaddress=0.0.0.0 connectport=5000 connectaddress=172.20.0.x
```
