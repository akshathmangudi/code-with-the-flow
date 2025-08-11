# Code with the Flow

**Code with the Flow** is a generative AI application that allows users to create, preview, and deploy single-page web applications from a natural language prompt. It is designed to be a seamless and intuitive tool for rapid prototyping and development, enabling you to bring your ideas to life by simply describing them.

## Features

-   **AI-Powered Creation**: Generate single-page applications using natural language prompts.
-   **Live Previews**: Instantly get a public URL to preview your creations in real-time. Our preview system runs on a tiny VPS and utilizes a paid plan to spin up multiple, stable port-forwarded previews from a single configuration file.
-   **Iterative Development**: Modify and update your application with follow-up prompts.
-   **One-Command Deployment**: Deploy your finished application to a permanent public URL with a single command.
-   **WhatsApp Integration**: Interact with the application through WhatsApp via Puch AI.

## How it Works

The application is built on a client-server architecture. The backend is a **Model Context Protocol (MCP)** server that exposes a set of tools for creating, previewing, and deploying applications. MCP is an open standard that allows for seamless communication between Large Language Model (LLM) applications and external systems.

When a user sends a prompt (e.g., via WhatsApp), the MCP server calls the appropriate tool, which then interacts with a generative model to create a complete, self-contained HTML file with inline CSS and JavaScript.

## Available Tools

The MCP server exposes the following tools:

-   **`vibecode`**:
    -   **Description**: Creates a simple, single-file web application from a prompt.
    -   **Usage**: Takes a natural language prompt and generates the initial HTML, CSS, and JavaScript for the application.
-   **`preview_app`**:
    -   **Description**: Creates a temporary, public URL to preview a generated application.
    -   **Usage**: Starts a local web server for the project and uses ngrok to create a secure public tunnel to it.
-   **`modify_app`**:
    -   **Description**: Modifies an existing application based on user feedback.
    -   **Usage**: Takes user feedback, reads the existing code, and uses an LLM to apply the requested changes.
-   **`deploy_app`**:
    -   **Description**: Deploys a web application to a permanent public URL using Surge.sh.
    -   **Usage**: Publishes the project to a unique `.surge.sh` domain.
-   **`validate`**:
    -   **Description**: A required tool for the MCP server to validate the connection.
    -   **Usage**: Used by the client to confirm a successful connection to the server.

## Project Structure

This repository contains the complete source code for the application.

```
.
├── .gitignore
├── pyproject.toml      # Project metadata and build configuration
├── README.md
├── requirements.txt    # Python dependencies
└── src/
    ├── app.py          # Defines the MCP tools for user interaction
    ├── config.py       # Application configuration
    ├── llm.py          # Functions for interacting with the generative AI model
    ├── main.py         # Main entry point to start the MCP server
    ├── preview.py      # Manages live application previews
    └── utils.py        # Utility functions
```

## Getting Started

### Prerequisites

-   Python 3.9+
-   Node.js and npm (for deployment via `surge`)
-   An account with a generative AI provider (e.g., Google AI for Gemini)
-   An ngrok account for creating public URLs.

### Installation

1.  Clone the repository:
    ```bash
    git clone https://github.com/your-username/code-with-the-flow.git
    cd code-with-the-flow
    ```

2.  Install the Python dependencies:
    ```bash
    pip install -r requirements.txt
    ```

3.  Install the deployment tool:
    ```bash
    npm install -g surge
    ```

### Configuration

1.  **Create a `.env` file** in the root of the project with the following environment variables:

    ```env
    GEMINI_API_KEY="your-gemini-api-key"
    GOOGLE_CLOUD_PROJECT="your-gcp-project-id"
    GOOGLE_CLOUD_LOCATION="your-gcp-location"
    PUCH_AI_API_KEY="your-puch-ai-api-key"
    MY_NUMBER="your-phone-number-for-validation"
    ```

3.  **Log in to Surge**:
    Run the following command in your terminal to log in to your Surge.sh account. This is required for deployment.
    ```bash
    npx surge login
    ```

## Usage

### Running the Server Locally

Once you have everything set up, you can start the application by running the following command:

```bash
python src/main.py
```

This will start the MCP server and create the ngrok tunnels. You will see a public URL for your MCP server in the console output.

### Integrating with Puch AI's WhatsApp Server

This application is designed to be used as a tool server for an LLM agent, such as one connected to WhatsApp via [Puch AI](https://puch.ai/).

To integrate:

1.  Start the `code-with-the-flow` server as described above.
2.  The console will output a public URL for the MCP server (e.g., `https://<unique-id>.ngrok.io/mcp`).
3.  In your Puch AI agent settings, add a new tool server and provide this URL.
4.  You can now interact with the application by sending messages to your Puch AI-powered WhatsApp number. For example:
    -   `"Create a pomodoro timer app"`
    -   `"Show me a preview"`
    -   `"Make the background dark blue"`
    -   `"Deploy it"`
