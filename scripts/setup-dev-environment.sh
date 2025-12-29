#!/bin/bash

set -euo pipefail

# Development Environment Setup Script for Pricing Agent
# This script sets up a complete development environment

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Script configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
PYTHON_VERSION="3.11"
NODE_VERSION="20"
POETRY_VERSION="1.8.2"

# Default values
SKIP_SYSTEM_DEPS=false
SKIP_DOCKER=false
SKIP_K8S=false
FORCE_REINSTALL=false
DEV_MODE="full"  # full, minimal, docker-only

# Logging functions
log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')] $1${NC}"
}

warn() {
    echo -e "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')] WARNING: $1${NC}" >&2
}

error() {
    echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ERROR: $1${NC}" >&2
    exit 1
}

info() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')] INFO: $1${NC}"
}

# Help function
show_help() {
    cat << EOF
Pricing Agent Development Environment Setup

This script sets up a complete development environment for the Pricing Agent project.

Usage: $0 [OPTIONS]

OPTIONS:
    --mode MODE                 Setup mode (full|minimal|docker-only) [default: full]
    --skip-system-deps         Skip system dependencies installation
    --skip-docker              Skip Docker setup
    --skip-k8s                 Skip Kubernetes tools setup
    --force-reinstall          Force reinstallation of all tools
    -h, --help                 Show this help message

SETUP MODES:
    full        - Complete setup with all tools and dependencies
    minimal     - Basic Python/Poetry setup only
    docker-only - Docker and containerization tools only

WHAT THIS SCRIPT DOES:
    • Installs system dependencies (Python, Node.js, etc.)
    • Sets up Poetry for Python dependency management
    • Configures Docker and Docker Compose
    • Installs Kubernetes tools (kubectl, helm, kustomize)
    • Sets up development databases (PostgreSQL, Redis)
    • Configures pre-commit hooks
    • Creates development environment files
    • Installs VS Code extensions (if available)

PREREQUISITES:
    • Linux or macOS operating system
    • Internet connection for downloading dependencies
    • sudo privileges for system package installation

EXAMPLES:
    # Full development setup
    $0

    # Minimal setup for Python development only
    $0 --mode minimal

    # Docker-only setup for containerized development
    $0 --mode docker-only

    # Force reinstall all tools
    $0 --force-reinstall
EOF
}

# Parse command line arguments
parse_args() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            --mode)
                DEV_MODE="$2"
                shift 2
                ;;
            --skip-system-deps)
                SKIP_SYSTEM_DEPS=true
                shift
                ;;
            --skip-docker)
                SKIP_DOCKER=true
                shift
                ;;
            --skip-k8s)
                SKIP_K8S=true
                shift
                ;;
            --force-reinstall)
                FORCE_REINSTALL=true
                shift
                ;;
            -h|--help)
                show_help
                exit 0
                ;;
            *)
                error "Unknown option: $1"
                ;;
        esac
    done

    # Validate mode
    if [[ ! "$DEV_MODE" =~ ^(full|minimal|docker-only)$ ]]; then
        error "Invalid mode: $DEV_MODE. Must be one of: full, minimal, docker-only"
    fi
}

# Detect operating system
detect_os() {
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        if command -v apt-get &> /dev/null; then
            OS="ubuntu"
            PACKAGE_MANAGER="apt"
        elif command -v yum &> /dev/null; then
            OS="centos"
            PACKAGE_MANAGER="yum"
        elif command -v dnf &> /dev/null; then
            OS="fedora"
            PACKAGE_MANAGER="dnf"
        else
            error "Unsupported Linux distribution"
        fi
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        OS="macos"
        PACKAGE_MANAGER="brew"
    else
        error "Unsupported operating system: $OSTYPE"
    fi
    
    log "Detected OS: $OS with package manager: $PACKAGE_MANAGER"
}

# Check if command exists
command_exists() {
    command -v "$1" &> /dev/null
}

# Install system dependencies
install_system_dependencies() {
    if [[ "$SKIP_SYSTEM_DEPS" == "true" ]]; then
        warn "Skipping system dependencies installation"
        return
    fi

    log "Installing system dependencies..."

    case $PACKAGE_MANAGER in
        apt)
            sudo apt-get update
            sudo apt-get install -y \
                curl \
                wget \
                git \
                build-essential \
                libssl-dev \
                zlib1g-dev \
                libbz2-dev \
                libreadline-dev \
                libsqlite3-dev \
                libncursesw5-dev \
                xz-utils \
                tk-dev \
                libxml2-dev \
                libxmlsec1-dev \
                libffi-dev \
                liblzma-dev \
                postgresql-client \
                redis-tools \
                jq \
                unzip
            ;;
        yum|dnf)
            sudo $PACKAGE_MANAGER update -y
            sudo $PACKAGE_MANAGER install -y \
                curl \
                wget \
                git \
                gcc \
                gcc-c++ \
                make \
                openssl-devel \
                bzip2-devel \
                libffi-devel \
                zlib-devel \
                readline-devel \
                sqlite-devel \
                xz-devel \
                tk-devel \
                postgresql \
                redis \
                jq \
                unzip
            ;;
        brew)
            # Update Homebrew
            brew update
            
            # Install dependencies
            brew install \
                curl \
                wget \
                git \
                openssl \
                readline \
                sqlite3 \
                xz \
                zlib \
                postgresql@15 \
                redis \
                jq \
                unzip || true  # Don't fail if already installed
            ;;
        *)
            error "Unsupported package manager: $PACKAGE_MANAGER"
            ;;
    esac

    log "System dependencies installed successfully"
}

# Install Python via pyenv
install_python() {
    if [[ "$DEV_MODE" == "docker-only" ]]; then
        return
    fi

    log "Setting up Python $PYTHON_VERSION..."

    # Install pyenv if not exists
    if ! command_exists pyenv; then
        log "Installing pyenv..."
        curl -L https://github.com/pyenv/pyenv-installer/raw/master/bin/pyenv-installer | bash
        
        # Add pyenv to PATH
        export PATH="$HOME/.pyenv/bin:$PATH"
        eval "$(pyenv init --path)"
        eval "$(pyenv init -)"
        
        # Add to shell profile
        SHELL_PROFILE=""
        if [[ -f "$HOME/.bashrc" ]]; then
            SHELL_PROFILE="$HOME/.bashrc"
        elif [[ -f "$HOME/.zshrc" ]]; then
            SHELL_PROFILE="$HOME/.zshrc"
        fi
        
        if [[ -n "$SHELL_PROFILE" ]]; then
            echo 'export PATH="$HOME/.pyenv/bin:$PATH"' >> "$SHELL_PROFILE"
            echo 'eval "$(pyenv init --path)"' >> "$SHELL_PROFILE"
            echo 'eval "$(pyenv init -)"' >> "$SHELL_PROFILE"
        fi
    fi

    # Install Python version if not available
    if ! pyenv versions --bare | grep -q "^$PYTHON_VERSION"; then
        log "Installing Python $PYTHON_VERSION..."
        pyenv install "$PYTHON_VERSION"
    fi

    # Set Python version for project
    cd "$PROJECT_ROOT"
    pyenv local "$PYTHON_VERSION"
    
    log "Python $PYTHON_VERSION configured successfully"
}

# Install Poetry
install_poetry() {
    if [[ "$DEV_MODE" == "docker-only" ]]; then
        return
    fi

    if command_exists poetry && [[ "$FORCE_REINSTALL" == "false" ]]; then
        log "Poetry already installed"
        return
    fi

    log "Installing Poetry $POETRY_VERSION..."

    # Install Poetry
    curl -sSL https://install.python-poetry.org | python3 - --version "$POETRY_VERSION"
    
    # Add Poetry to PATH
    export PATH="$HOME/.local/bin:$PATH"
    
    # Configure Poetry
    poetry config virtualenvs.in-project true
    poetry config virtualenvs.create true
    
    log "Poetry installed and configured successfully"
}

# Install Node.js and npm
install_nodejs() {
    if [[ "$DEV_MODE" == "minimal" ]]; then
        return
    fi

    log "Setting up Node.js $NODE_VERSION..."

    # Install Node Version Manager (nvm) if not exists
    if ! command_exists nvm; then
        log "Installing nvm..."
        curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.0/install.sh | bash
        
        # Source nvm
        export NVM_DIR="$HOME/.nvm"
        [ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
    fi

    # Install Node.js
    nvm install "$NODE_VERSION"
    nvm use "$NODE_VERSION"
    nvm alias default "$NODE_VERSION"

    # Install global packages
    npm install -g npm@latest
    npm install -g yarn
    npm install -g @angular/cli
    npm install -g artillery  # For load testing

    log "Node.js $NODE_VERSION installed successfully"
}

# Install Docker
install_docker() {
    if [[ "$SKIP_DOCKER" == "true" ]]; then
        warn "Skipping Docker installation"
        return
    fi

    if command_exists docker && [[ "$FORCE_REINSTALL" == "false" ]]; then
        log "Docker already installed"
        return
    fi

    log "Installing Docker..."

    case $OS in
        ubuntu)
            # Add Docker's official GPG key
            sudo apt-get update
            sudo apt-get install -y ca-certificates curl gnupg
            sudo install -m 0755 -d /etc/apt/keyrings
            curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
            sudo chmod a+r /etc/apt/keyrings/docker.gpg

            # Add the repository to Apt sources
            echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
            
            sudo apt-get update
            sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
            ;;
        centos|fedora)
            sudo $PACKAGE_MANAGER install -y yum-utils
            sudo yum-config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo
            sudo $PACKAGE_MANAGER install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
            ;;
        macos)
            # On macOS, recommend Docker Desktop
            log "Please install Docker Desktop from https://www.docker.com/products/docker-desktop"
            log "Or use: brew install --cask docker"
            return
            ;;
    esac

    # Add user to docker group
    sudo usermod -aG docker "$USER"
    
    # Start Docker service
    sudo systemctl start docker
    sudo systemctl enable docker

    log "Docker installed successfully"
    warn "Please log out and back in for Docker group membership to take effect"
}

# Install Kubernetes tools
install_kubernetes_tools() {
    if [[ "$SKIP_K8S" == "true" ]] || [[ "$DEV_MODE" == "minimal" ]]; then
        warn "Skipping Kubernetes tools installation"
        return
    fi

    log "Installing Kubernetes tools..."

    # Install kubectl
    if ! command_exists kubectl || [[ "$FORCE_REINSTALL" == "true" ]]; then
        log "Installing kubectl..."
        curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
        sudo install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl
        rm kubectl
    fi

    # Install Helm
    if ! command_exists helm || [[ "$FORCE_REINSTALL" == "true" ]]; then
        log "Installing Helm..."
        curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash
    fi

    # Install kustomize
    if ! command_exists kustomize || [[ "$FORCE_REINSTALL" == "true" ]]; then
        log "Installing kustomize..."
        curl -s "https://raw.githubusercontent.com/kubernetes-sigs/kustomize/master/hack/install_kustomize.sh" | bash
        sudo mv kustomize /usr/local/bin/
    fi

    # Install kind for local Kubernetes
    if ! command_exists kind || [[ "$FORCE_REINSTALL" == "true" ]]; then
        log "Installing kind..."
        curl -Lo ./kind https://kind.sigs.k8s.io/dl/v0.20.0/kind-linux-amd64
        chmod +x ./kind
        sudo mv ./kind /usr/local/bin/kind
    fi

    log "Kubernetes tools installed successfully"
}

# Setup project dependencies
setup_project_dependencies() {
    if [[ "$DEV_MODE" == "docker-only" ]]; then
        return
    fi

    log "Setting up project dependencies..."

    cd "$PROJECT_ROOT"

    # Install Python dependencies
    if [[ -f "pyproject.toml" ]]; then
        log "Installing Python dependencies with Poetry..."
        poetry install --with dev
    fi

    # Install pre-commit hooks
    if command_exists poetry; then
        log "Setting up pre-commit hooks..."
        poetry run pre-commit install
        poetry run pre-commit install --hook-type commit-msg
    fi

    log "Project dependencies installed successfully"
}

# Setup development databases
setup_development_databases() {
    if [[ "$DEV_MODE" == "minimal" ]]; then
        return
    fi

    log "Setting up development databases..."

    # Create development docker-compose override
    cat > "$PROJECT_ROOT/docker-compose.override.yml" << 'EOF'
version: '3.8'

services:
  postgres:
    ports:
      - "5432:5432"
    environment:
      POSTGRES_DB: pricing_agent_dev
      POSTGRES_USER: dev_user
      POSTGRES_PASSWORD: dev_password

  redis:
    ports:
      - "6379:6379"

  # Development database GUI tools
  pgadmin:
    image: dpage/pgadmin4:latest
    environment:
      PGADMIN_DEFAULT_EMAIL: admin@dev.local
      PGADMIN_DEFAULT_PASSWORD: admin123
    ports:
      - "5050:80"
    depends_on:
      - postgres

  redis-commander:
    image: rediscommander/redis-commander:latest
    environment:
      REDIS_HOSTS: local:redis:6379
    ports:
      - "8081:8081"
    depends_on:
      - redis
EOF

    log "Development database configuration created"
    log "Run 'docker-compose up -d postgres redis pgadmin redis-commander' to start development databases"
}

# Setup environment files
setup_environment_files() {
    log "Setting up environment files..."

    cd "$PROJECT_ROOT"

    # Create development .env file if it doesn't exist
    if [[ ! -f ".env.dev" ]]; then
        log "Creating development environment file..."
        cat > ".env.dev" << 'EOF'
# Development Environment Configuration
DEBUG=true
SECRET_KEY=dev-secret-key-change-me
ENVIRONMENT=development

# Database Configuration
DATABASE_URL=postgres://dev_user:dev_password@localhost:5432/pricing_agent_dev
POSTGRES_DB=pricing_agent_dev
POSTGRES_USER=dev_user
POSTGRES_PASSWORD=dev_password

# Redis Configuration
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/0

# Application URLs
DJANGO_URL=http://localhost:8000
ML_SERVICE_URL=http://localhost:8001
ALLOWED_HOSTS=localhost,127.0.0.1,0.0.0.0
ALLOWED_ORIGINS=http://localhost:8000,http://127.0.0.1:8000

# Development Tools
DJANGO_DEBUG_TOOLBAR=true
DJANGO_EXTENSIONS_ENABLED=true

# Logging
LOG_LEVEL=DEBUG
DJANGO_LOG_LEVEL=DEBUG

# External Services (disabled for development)
EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
SENTRY_DSN=

# Development Features
ENABLE_API_DOCS=true
ENABLE_SILK_PROFILING=true
SKIP_MIGRATIONS=false
EOF
    fi

    # Create symbolic link to development env
    if [[ ! -f ".env" ]]; then
        ln -sf .env.dev .env
        log "Linked .env to .env.dev"
    fi

    log "Environment files configured successfully"
}

# Install VS Code extensions
install_vscode_extensions() {
    if ! command_exists code; then
        log "VS Code not found, skipping extensions installation"
        return
    fi

    log "Installing VS Code extensions..."

    # Python extensions
    code --install-extension ms-python.python
    code --install-extension ms-python.black-formatter
    code --install-extension ms-python.isort
    code --install-extension ms-python.mypy-type-checker
    code --install-extension ms-python.pylint

    # Docker extensions
    code --install-extension ms-azuretools.vscode-docker

    # Kubernetes extensions
    code --install-extension ms-kubernetes-tools.vscode-kubernetes-tools

    # Git extensions
    code --install-extension eamodio.gitlens

    # General productivity
    code --install-extension esbenp.prettier-vscode
    code --install-extension bradlc.vscode-tailwindcss
    code --install-extension ms-vscode.vscode-json

    # Create VS Code workspace settings
    mkdir -p "$PROJECT_ROOT/.vscode"
    cat > "$PROJECT_ROOT/.vscode/settings.json" << 'EOF'
{
    "python.defaultInterpreterPath": "./.venv/bin/python",
    "python.linting.enabled": true,
    "python.linting.pylintEnabled": true,
    "python.linting.mypyEnabled": true,
    "python.formatting.provider": "black",
    "python.sortImports.args": ["--profile", "black"],
    "[python]": {
        "editor.formatOnSave": true,
        "editor.codeActionsOnSave": {
            "source.organizeImports": true
        }
    },
    "files.exclude": {
        "**/__pycache__": true,
        "**/*.pyc": true,
        "**/node_modules": true,
        "**/.git": false,
        "**/.venv": true
    },
    "docker.defaultRegistryPath": "your-registry.com"
}
EOF

    log "VS Code extensions and settings configured successfully"
}

# Create development scripts
create_development_scripts() {
    log "Creating development scripts..."

    # Create scripts directory
    mkdir -p "$PROJECT_ROOT/scripts/dev"

    # Create development server script
    cat > "$PROJECT_ROOT/scripts/dev/run-dev-server.sh" << 'EOF'
#!/bin/bash
set -euo pipefail

# Start development servers
echo "Starting Pricing Agent development servers..."

# Start databases
docker-compose up -d postgres redis

# Wait for databases
echo "Waiting for databases..."
sleep 10

# Run Django migrations
poetry run python django_app/manage.py migrate

# Start Django development server in background
echo "Starting Django server..."
poetry run python django_app/manage.py runserver 0.0.0.0:8000 &
DJANGO_PID=$!

# Start FastAPI development server in background
echo "Starting FastAPI server..."
cd fastapi_ml
poetry run uvicorn main:app --host 0.0.0.0 --port 8001 --reload &
FASTAPI_PID=$!
cd ..

# Start Celery worker in background
echo "Starting Celery worker..."
poetry run celery -A pricing_agent worker --loglevel=info &
CELERY_PID=$!

# Wait for interrupt
echo "Development servers running:"
echo "  Django: http://localhost:8000"
echo "  FastAPI: http://localhost:8001"
echo "  PgAdmin: http://localhost:5050"
echo "  Redis Commander: http://localhost:8081"
echo ""
echo "Press Ctrl+C to stop all servers"

trap "kill $DJANGO_PID $FASTAPI_PID $CELERY_PID 2>/dev/null || true" INT TERM

wait
EOF

    chmod +x "$PROJECT_ROOT/scripts/dev/run-dev-server.sh"

    # Create test runner script
    cat > "$PROJECT_ROOT/scripts/dev/run-tests.sh" << 'EOF'
#!/bin/bash
set -euo pipefail

echo "Running Pricing Agent tests..."

# Start test databases
docker-compose up -d postgres redis
sleep 5

# Run Django tests
echo "Running Django tests..."
poetry run pytest django_app/tests/ -v --cov=django_app

# Run FastAPI tests
echo "Running FastAPI tests..."
poetry run pytest fastapi_ml/tests/ -v --cov=fastapi_ml

# Run integration tests
echo "Running integration tests..."
docker-compose -f docker-compose.yml up -d
sleep 30
poetry run pytest tests/integration/ -v
docker-compose down

echo "All tests completed!"
EOF

    chmod +x "$PROJECT_ROOT/scripts/dev/run-tests.sh"

    # Create linting script
    cat > "$PROJECT_ROOT/scripts/dev/run-linting.sh" << 'EOF'
#!/bin/bash
set -euo pipefail

echo "Running code quality checks..."

# Black formatting
echo "Running Black formatter..."
poetry run black --check .

# Ruff linting
echo "Running Ruff linter..."
poetry run ruff check .

# MyPy type checking
echo "Running MyPy type checker..."
poetry run mypy django_app fastapi_ml

# Django system checks
echo "Running Django system checks..."
poetry run python django_app/manage.py check

echo "All code quality checks completed!"
EOF

    chmod +x "$PROJECT_ROOT/scripts/dev/run-linting.sh"

    log "Development scripts created successfully"
}

# Print setup summary
print_setup_summary() {
    log "Development environment setup completed!"
    
    echo ""
    echo "=================================="
    echo "SETUP SUMMARY"
    echo "=================================="
    echo ""
    echo "Mode: $DEV_MODE"
    echo "OS: $OS"
    echo "Project Root: $PROJECT_ROOT"
    echo ""
    
    if [[ "$DEV_MODE" != "docker-only" ]]; then
        echo "Python: $(python3 --version 2>/dev/null || echo 'Not available')"
        if command_exists poetry; then
            echo "Poetry: $(poetry --version)"
        fi
    fi
    
    if [[ "$DEV_MODE" != "minimal" ]]; then
        if command_exists node; then
            echo "Node.js: $(node --version)"
        fi
        if command_exists docker; then
            echo "Docker: $(docker --version)"
        fi
    fi
    
    if [[ "$DEV_MODE" == "full" ]]; then
        if command_exists kubectl; then
            echo "kubectl: $(kubectl version --client --short 2>/dev/null || echo 'Not available')"
        fi
        if command_exists helm; then
            echo "Helm: $(helm version --short 2>/dev/null || echo 'Not available')"
        fi
    fi
    
    echo ""
    echo "=================================="
    echo "NEXT STEPS"
    echo "=================================="
    echo ""
    echo "1. Start development environment:"
    echo "   ./scripts/dev/run-dev-server.sh"
    echo ""
    echo "2. Run tests:"
    echo "   ./scripts/dev/run-tests.sh"
    echo ""
    echo "3. Check code quality:"
    echo "   ./scripts/dev/run-linting.sh"
    echo ""
    echo "4. Access development services:"
    echo "   • Django: http://localhost:8000"
    echo "   • FastAPI: http://localhost:8001"
    echo "   • PgAdmin: http://localhost:5050 (admin@dev.local / admin123)"
    echo "   • Redis Commander: http://localhost:8081"
    echo ""
    echo "5. VS Code workspace:"
    echo "   code ."
    echo ""
    
    if [[ "$OS" != "macos" ]] && groups "$USER" | grep -q docker; then
        warn "Please log out and back in for Docker group membership to take effect"
    fi
}

# Main function
main() {
    log "Starting Pricing Agent development environment setup..."
    
    parse_args "$@"
    detect_os
    
    # Run setup steps based on mode
    case $DEV_MODE in
        full)
            install_system_dependencies
            install_python
            install_poetry
            install_nodejs
            install_docker
            install_kubernetes_tools
            setup_project_dependencies
            setup_development_databases
            setup_environment_files
            install_vscode_extensions
            create_development_scripts
            ;;
        minimal)
            install_system_dependencies
            install_python
            install_poetry
            setup_project_dependencies
            setup_environment_files
            install_vscode_extensions
            create_development_scripts
            ;;
        docker-only)
            install_system_dependencies
            install_docker
            install_kubernetes_tools
            setup_development_databases
            setup_environment_files
            create_development_scripts
            ;;
    esac
    
    print_setup_summary
}

# Trap to handle script interruption
trap 'error "Setup interrupted"' INT TERM

# Run main function with all arguments
main "$@"