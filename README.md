
## Description

This repository contains the source code and resources required to create and train a conversational agent using RASA, an open-source platform for chatbot and virtual assistant development.

## Repository Structure

The repository is organized as follows:

- `data/`: Contains training and evaluation files for the RASA model.
- `models/`: Holds the latest pre-trained models of the conversational agent.
- `actions/`: Includes custom actions with calls to external modules and databases.
- `config.yml`: Defines the training configuration for RASA NLU and RASA Core.
- `domain.yml`: Defines the domain of the conversational agent, including intents, actions, entities, and slots.
- `credentials.yml`: Contains credentials for integration with external platforms (in this setting we used Telegram)


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

6. Start the RASA server and the SDK server (in a separate terminal) to interact with the agent:

    ```bash
    rasa run
    ```

    ```bash
    rasa run actions
    ```
