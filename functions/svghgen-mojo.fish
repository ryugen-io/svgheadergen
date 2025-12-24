function svghgen-mojo --description 'SVG header generator (Mojo/pixi)'
    set -l project_dir (dirname (status --current-filename))/..

    # Check if pixi is available
    if not command -v pixi &>/dev/null
        echo "Error: pixi not installed"
        echo "Install pixi: curl -fsSL https://pixi.sh/install.sh | bash"
        return 1
    end

    # Run via pixi in the project directory
    pixi run -C $project_dir mojo svg_gen.mojo $argv
end
