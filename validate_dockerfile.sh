
#!/bin/bash

echo "Validating Dockerfile..."

# Check if Dockerfile exists
if [ ! -f Dockerfile ]; then
    echo "Error: Dockerfile not found"
    exit 1
fi

# Check for syntax errors
if ! grep -qE '^FROM' Dockerfile; then
    echo "Error: FROM instruction missing"
    exit 1
fi

if ! grep -qE '^RUN' Dockerfile; then
    echo "Error: No RUN instructions found"
    exit 1
fi

if ! grep -qE '^CMD' Dockerfile; then
    echo "Error: CMD instruction missing"
    exit 1
fi

# Check for best practices
if grep -qE '^USER root' Dockerfile; then
    echo "Warning: Explicitly setting user to root is not recommended"
fi

if ! grep -qE '^USER' Dockerfile; then
    echo "Warning: No USER instruction found. It's recommended to run as non-root"
fi

echo "Dockerfile validation complete"
