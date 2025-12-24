function svghgen --description 'SVG header generator from ASCII art (Python/pipx)'
    # Check if svghgen is installed (pipx)
    if not command -v svghgen &>/dev/null
        echo "Error: svghgen not installed"
        echo "Run: cd ~/code/github.com/ryugen-io/svghgen && ./install.sh"
        return 1
    end

    # Just pass through to the actual command
    command svghgen $argv
end
