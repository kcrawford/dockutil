set | grep -q '^BASH_VERSION=' || echo "use bash for your shell"
set | grep -q '^BASH_VERSION=' || exit 1

# Note: BASHRC unsets PYTHONPATH
source ~/.bashrc

# Set Python environment optimizations
export PYTHONUNBUFFERED=1
export PYTHONDONTWRITEBYTECODE=1

