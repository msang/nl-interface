
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
- `endopoints.yml`: Contains the endpoint for the rasa action server and NLG server
- `ProsunAI/`: folder that contains the code to run the GUI built with Android Studio


## Requirements
To run the agent, please make sure you have the following installed:
- Python 3.9
- Rasa 3.6
- Rasa SDK


You might also need to retrieve your API credentials for the following services:
- [Ngrok](https://ngrok.com/): to expose the Rasa backend on a public URL
- [SolarEdge Monitoring Platform](https://www.solaredge.com/it/products/software-tools/monitoring-platform): to retrieve your energy data on consumption and solar production
 

## Getting Started

To begin using the agent, follow these steps:

1. Clone the repository and switch to the right branch:

    ```bash
    git clone https://github.com/msang/nl-interface.git
	cd nl-interface
	git checkout dev-nest
    ```

2. Save your API credentials in an `.env` file within the `actions/` folder.

3. Create and activate a virtual environment 

    ```bash
    python -m venv rasa
    source rasa/bin/activate   
    ```

4. Install the necessary dependencies:

    ```bash
    pip install -r requirements.txt
    ```

5. Train the RASA model with the training data already available in data/nlu.yml:

    ```bash
    rasa train
    ```

4. Chat with the agent via command line using the following script:
  
  ```bash

  python  chat.py
  ```
  
   The script automatically starts the RASA server, the SDK server and the NLG server.
   

5. To interact with the agent via GUI, use the `ProsunAI` demo (described below).

## ProsunAI

+ Key features

    - Chat interaction: Users can communicate with the conversational agent through a simple and direct chat.
    - Real-time answers: The app is able to provide quick and relevant answers based on the text entered by the user.
    - User-friendly interface: The app is designed to be easy to use, making the user experience smooth and pleasant.

+ How it works

    - Users can download the ProsunAI project directly from this github repository. Then, opening it with Android Studio, they can modify the ngrok link, with the one they will create themselves, found in the following location: 

            "ProsunAI/app/src/main/java/com/example/ProsunAI"

      Finally, they can test the code using a virtual device or by downloading the apk file for debugging.

    - Starting the conversation: Once the testing of the mobile application is run, the user can start chatting with the conversational agent via the `chat.py` script provided in this repo.
 
    - Connection to the Rasa server: ProsunAI uses ngrok to establish a secure connection with the Rasa server, which processes requests and outputs replies based on the text entered by the user.
 


