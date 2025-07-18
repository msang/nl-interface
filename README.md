
## Description

This repository contains the source code and resources required to run your own conversational agent for energy feedback using Telegram as messaging channel.


## Repository Structure

The repository is organized as follows:

- `data/`: Contains training and evaluation files for the RASA model.
- `models/`: Holds the latest pre-trained models of the conversational agent.
- `actions/`: Includes custom actions with calls to external modules .
- `config.yml`: Defines the training configuration for RASA NLU and RASA Core.
- `domain.yml`: Defines the domain of the conversational agent, including intents, actions, entities, and slots.
- `credentials.yml`: Contains credentials for integration with external interfaces via REST and Socket.IO channels
- `endopoints.yml`: Contains the endpoint for the rasa action server and NLG server



## Requirements
To run the agent, please make sure you have the following installed:
- Python 3.9
- Rasa 3.6
- Rasa SDK


You might also need to retrieve your API credentials for the following services:
- [Ngrok](https://ngrok.com/): to expose the Rasa backend on a public URL
- [SolarEdge Monitoring Platform](https://www.solaredge.com/it/products/software-tools/monitoring-platform): to retrieve energy data on consumption and solar production
 


## Getting Started

To begin using the agent, follow these steps:

1. Clone the repository and swith to the right branch:

    ```bash
    git clone https://github.com/msang/nl-interface.git
	cd nl-interface
	git checkout dev-nest
    ```

2. Save your API credentials in an .env file  

3. Create and activate a virtual environment 

4. Chat with the agent via command line using the following script:
  
  ```bash

  python  chat.py
  ```
