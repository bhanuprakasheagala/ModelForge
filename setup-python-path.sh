if [[ $(uname -m) == "arm64" ]]; then
    echo 'export PATH="/opt/homebrew/opt/python@3.12/bin:$PATH"' >> ~/.zshrc
else
    echo 'export PATH="/usr/local/opt/python@3.12/bin:$PATH"' >> ~/.zshrc
fi

