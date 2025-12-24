function svghgen-mojo --description 'SVG header generator (Mojo/pixi)'
    set -l project_dir ~/code/github.com/ryugen-io/svghgen

    # Check if pixi is available
    if not command -v pixi &>/dev/null
        echo "Error: pixi not installed"
        echo "Install pixi: curl -fsSL https://pixi.sh/install.sh | bash"
        return 1
    end

    # Check if project directory exists
    if not test -d $project_dir
        echo "Error: svghgen directory not found at $project_dir"
        return 1
    end

    # Run via pixi in the project directory
    cd $project_dir && pixi run mojo svg_gen.mojo $argv
end
