# Vibe Coder - Puch AI WhatsApp Integration

A vibe-coding app that integrates with Puch AI's WhatsApp MCP server to create applications through chat messages.

## 🚀 Features

- **WhatsApp Integration**: Use `/mcp <prompt>` syntax to create applications
- **Progress Reporting**: Real-time updates sent back to WhatsApp
- **Code Generation**: Creates Flask applications with proper structure
- **Validation**: Checks for syntax errors and requirements
- **GitHub Deployment**: Automatic deployment to GitHub (placeholder)
- **Feedback Loop**: Validates requirements and provides user feedback

## 🛠️ Setup

### 1. Install Dependencies

```bash
# Activate your virtual environment
source .venv/bin/activate.fish

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Environment

Copy the example configuration:
```bash
cp config.env.example .env
```

Edit `.env` with your actual values:
```env
PUCH_AI_API_KEY=your_puch_ai_api_key_here
PUCH_AI_WHATSAPP_WEBHOOK_URL=https://your-domain.com/webhook
VIBE_CODER_SERVER_URL=http://localhost:8000
GITHUB_TOKEN=your_github_token_here
GITHUB_USERNAME=your_github_username
```

### 3. Start the Server

```bash
# Start the MCP server
uvicorn vibe-coder.main:app --reload
```

The server will be available at `http://localhost:8000`

## 🧪 Testing

### Local Testing

Run the test script to verify everything works:

```bash
python test_puch_integration.py
```

### Manual Testing

1. **Test the code_app tool**:
   ```bash
   curl -X POST http://localhost:8000/tools/code_app \
     -H "Content-Type: application/json" \
     -d '{"prompt": "Create a simple todo app"}'
   ```

2. **Test the webhook endpoint**:
   ```bash
   curl -X POST http://localhost:8000/webhook \
     -H "Content-Type: application/json" \
     -d '{"message": "Create a weather app", "user_id": "test_user"}'
   ```

## 📱 WhatsApp Integration with Puch AI

### How it Works

1. **User sends message**: `/mcp Create a simple todo app`
2. **Puch AI parses**: Extracts the prompt after `/mcp `
3. **Calls your MCP server**: Invokes the `code_app` tool
4. **Progress updates**: Real-time feedback sent to WhatsApp
5. **Validation**: Checks if requirements are met
6. **Deployment**: Automatically deploys to GitHub
7. **Live demo**: Provides link to running application

### Available Tools

- `code_app(prompt: str)` - Creates a new Flask application
- `validate_project(project_name: str)` - Validates the created project
- `deploy_to_github(project_name: str)` - Deploys project to GitHub

### Progress Reporting

The tools use the MCP Context to send real-time updates:

```python
if ctx:
    await ctx.info("🎯 Starting to code app...")
    await ctx.info("📁 Creating project directory...")
    await ctx.info("✅ Project created successfully!")
```

## 🔧 Development

### Project Structure

```
vibe-coder/
├── main.py              # Main MCP server
├── test_puch_integration.py  # Test script
└── config.env.example   # Configuration template
```

### Adding New Tools

To add a new tool to your MCP server:

```python
@app.tool()
async def my_new_tool(param: str, ctx: Optional[Context] = None) -> str:
    """Description of what the tool does"""
    if ctx:
        await ctx.info("Starting...")
    
    # Your tool logic here
    
    return "Success message"
```

### Environment Variables

- `PUCH_AI_API_KEY`: Your Puch AI API key
- `VIBE_CODER_SERVER_URL`: Your server's public URL
- `GITHUB_TOKEN`: GitHub personal access token
- `GITHUB_USERNAME`: Your GitHub username

## 🚀 Deployment

### For Puch AI Integration

1. **Deploy to a public server** (Heroku, Railway, etc.)
2. **Update your webhook URL** in Puch AI dashboard
3. **Configure environment variables** on your server
4. **Test the integration** with real WhatsApp messages

### Example Deployment (Heroku)

```bash
# Create Procfile
echo "web: uvicorn vibe-coder.main:app --host 0.0.0.0 --port \$PORT" > Procfile

# Deploy to Heroku
heroku create your-vibe-coder-app
git add .
git commit -m "Deploy vibe-coder"
git push heroku main
```

## 🎯 Puch AI Hackathon

This project is built for the [Puch AI Hackathon](https://puch.ai/hack).

### Key Features for Hackathon

- ✅ **WhatsApp Integration**: `/mcp <prompt>` syntax
- ✅ **Progress Updates**: Real-time feedback to users
- ✅ **Code Generation**: Creates working Flask apps
- ✅ **Validation**: Checks requirements and syntax
- ✅ **GitHub Deployment**: Automatic deployment (placeholder)
- ✅ **Live Demo**: Provides running application links

### Testing with Puch AI

1. **Get your API key** from the Puch AI hackathon
2. **Deploy your server** to a public URL
3. **Configure webhook** in Puch AI dashboard
4. **Test with WhatsApp**: Send `/mcp Create a weather app`
5. **Monitor progress**: Watch real-time updates in WhatsApp
6. **Check results**: Visit the deployed application

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## 📄 License

This project is built for the Puch AI Hackathon.

---

**Happy Coding! 🚀**
