
## Description

This repository contains the source code and resources required to run your own conversational agent for energy feedback from the command line.


## Repository Structure

The repository is organized as follows:

- `data/`: Contains training and evaluation files for the RASA model.
- `models/`: Holds the latest pre-trained models of the conversational agent.
- `actions/`: Includes custom actions with calls to external modules .
- `nlg/`: Includes the code to run the external NLG server
- `config.yml`: Defines the training configuration for RASA NLU and RASA Core.
- `domain.yml`: Defines the domain of the conversational agent, including intents, actions, entities, and slots.
- `credentials.yml`: Contains credentials for integration with external interfaces via REST and Socket.IO channels
- `endpoints.yml`: Contains the endpoint for the rasa action server and NLG server



## Requirements
To run the agent, please make sure you have the following installed:
- Python 3.10
- Rasa 3.6.21
- Rasa SDK 3.6.2


You might also need to retrieve your API credentials for the following services:
- [Ngrok](https://ngrok.com/): to expose the Rasa backend on a public URL
- [SolarEdge Monitoring Platform](https://www.solaredge.com/it/products/software-tools/monitoring-platform): to retrieve your energy data on consumption and solar production
 

## Getting Started

To begin using the agent, follow these steps:

1. Clone the repository:

    ```bash
    git clone https://github.com/msang/nl-interface.git
	cd nl-interface
    ```
	In case you want to switch to another branch:
	
	```bash
	git checkout dev-nest
    ```

2. Save your NGROK token in an `.env` of the main folder, and SolarEdge API credentials in a different `.env` file within the `actions/` folder.

3. Create and activate a virtual environment 

    ```bash
    python -m venv rasa
    source rasa/bin/activate   
    ```
	
	If you are using `pyenv`:
	
	```bash
    pyenv install 3.10
    pyenv virtualenv 3.10 <environment_name>   	
	cd nl-interface
	pyenv local <environment_name> 
    ```

4. Install the necessary dependencies:

    ```bash
    pip install -r requirements.txt
    ```

5. Train from scratch the RASA model with the training data already available in data/nlu.yml:

    ```bash
    rasa train
    ```

4. Chat with the agent via command line using the following script:
  
  ```bash

  python  chat.py
  ```
  
   The script automatically starts the RASA server, the RASA Actions server and the NLG server.
   

5. To interact with the agent via GUI, use the `ProsunAI` demo (see `dev-gui` branch).

