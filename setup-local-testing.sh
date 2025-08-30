#!/bin/bash

# VibeCoder Local Testing Setup Script
# This script sets up your local environment for testing with vibecode.akshath.tech

echo "🚀 Setting up VibeCoder local testing environment..."

# Check if running as root for /etc/hosts modification
if [ "$EUID" -ne 0 ]; then
    echo "⚠️  This script needs sudo access to modify /etc/hosts"
fi

# 1. Add local domain mapping to /etc/hosts
echo "📝 Adding domain mappings to /etc/hosts..."

# Backup original hosts file
sudo cp /etc/hosts /etc/hosts.backup.vibecode

# Add our domains
echo "" | sudo tee -a /etc/hosts
echo "# VibeCoder local testing domains" | sudo tee -a /etc/hosts
echo "127.0.0.1 vibecode.akshath.tech" | sudo tee -a /etc/hosts
echo "127.0.0.1 *.vibecode.akshath.tech" | sudo tee -a /etc/hosts

# 2. Clone the deployed projects repository if it doesn't exist
echo "📁 Setting up project repository..."
cd /home/akshathm/work/

if [ ! -d "vibecode-deployed-projects" ]; then
    echo "Cloning vibecode-deployed-projects repository..."
    git clone https://github.com/akshathmangudi/vibecode-deployed-projects.git
else
    echo "Repository already exists, pulling latest changes..."
    cd vibecode-deployed-projects
    git pull origin main
    cd ..
fi

# 3. Create necessary directories
echo "📂 Creating project directories..."
mkdir -p vibecode-deployed-projects/projects
mkdir -p vibecode/projects

# 4. Install and configure nginx (optional)
if command -v nginx &> /dev/null; then
    echo "✅ Nginx is already installed"
    echo "📋 To configure nginx, copy the nginx-local.conf to your nginx sites:"
    echo "   sudo cp /home/akshathm/work/vibecode/nginx-local.conf /etc/nginx/sites-available/vibecode-local"
    echo "   sudo ln -s /etc/nginx/sites-available/vibecode-local /etc/nginx/sites-enabled/"
    echo "   sudo nginx -t && sudo systemctl reload nginx"
else
    echo "⚠️  Nginx not found. Install with: sudo apt install nginx"
fi

# 5. Check Python environment
cd vibecode
if [ -d ".venv" ]; then
    echo "✅ Python virtual environment found"
else
    echo "📦 Creating Python virtual environment..."
    python3 -m venv .venv
fi

echo "🎉 Setup complete!"
echo ""
echo "📋 Next steps:"
echo "1. Activate virtual environment: source .venv/bin/activate"
echo "2. Install dependencies: uv pip install -r pyproject.toml"
echo "3. Configure Puch MCP client to connect to: http://vibecode.akshath.tech:8000/mcp"
echo "4. Start the server: python main.py"
echo "5. Test by creating a project and accessing: http://<project-name>.vibecode.akshath.tech"
echo ""
echo "🔧 Optional: Configure nginx for serving static files (see nginx-local.conf)"
echo "🗑️  To remove: sudo sed -i '/VibeCoder local testing/,+2d' /etc/hosts"
