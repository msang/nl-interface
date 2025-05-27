
## Description

This repository contains the source code and resources required to create and train a conversational agent using RASA.


## Repository Structure

The repository is organized as follows:

- `data/`: Contains training and evaluation files for the RASA model.
- `models/`: Holds the latest pre-trained models of the conversational agent.
- `actions/`: Includes custom actions with calls to external modules and APIs.
- `nlg/`: Includes the code to run the external NLG server
- `config.yml`: Defines the training configuration for RASA NLU and RASA Core.
- `domain.yml`: Defines the domain of the conversational agent, including intents, actions, entities, and slots.
- `credentials.yml`: Contains credentials for integration with external platforms (in this setting we just use the REST channel, for public URL exposure through NGROK)
- `endpoints.yml`: Contains the URL to the RASA Action (SDK) server


## Getting Started

To begin using the agent, follow these steps:

1. Clone the repository:

    ```bash
    git clone https://github.com/msang/nl-interface.git
    ```

2. Navigate to the project directory:

    ```bash
    cd nl-interface
    ```

3. Create and activate a virtual environment:

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

6. Start the RASA server, the SDK server and the NLG server (all in separate terminals) to interact with the agent:

    ```bash
    rasa run
    ```

    ```bash
    rasa run actions
    ```

    ```bash
    cd  nlg
    python nlg-server.py
    ```

7. To create a public URL for the agent, download and install NGROK, then run

   ```bash
    ngrok http 5005
    ```
   
## ProsunAI

Within the dev-gui branch, in this github repository, one can find the code for the Android mobile application named ProsunAi: it is designed to provide users with an intuitive conversational interface. 

Thanks to an advanced conversational agent, users can interact naturally and receive immediate answers to their questions.

+ Key features

    - Chat interaction: Users can communicate with the conversational agent through a simple and direct chat.

    - Real-time answers: The app is able to provide quick and relevant answers based on the text entered by the user.

    - User-friendly interface: The app is designed to be easy to use, making the user experience smooth and pleasant.

+ How it works

    - Downloading, editing and using the ProsunAI code: Users can download the ProsunAI project directly from this github repository. Then, opening it with Android Studio, they can modify the ngrok link, with the one they will create themselves, found in the following location 

            "ProsunAI/app/src/main/java/com/example/ProsunAI"

            Finally, they can test the code using a virtual device or by downloading the apk file for debugging.

    - Starting the conversation: Once the testing of the mobile application is run, the user can start chatting with the conversational agent.
 
    - Connection to the Rasa server: ProsunAI uses ngrok to establish a secure connection with the Rasa server, which processes requests and outputs replies based on the text entered by the user.
 
ProsunAI represents a step forward in human-computer interaction, offering a simple and direct way to get information and answers through a chat. With its intuitive interface, it is the ideal mobile application for those looking for an easy way to communicate with the conversational agent hosted on a Rasa server.
