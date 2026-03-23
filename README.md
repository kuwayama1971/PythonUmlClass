# PythonUmlClass
Create a python class diagram

Read this in other languages: [English](README.md), [日本語](README_JA.md)

## Setup
    for ubuntu
    $ sudo apt install plantuml
    $ apt install -y pip
    $ pip install astor

    install google-chrome
    $ echo "deb http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google.list
    $ wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add -
    $ apt update
    $ apt -y install google-chrome-stable

## Installation

Install the gem and add to the application's Gemfile by executing:

    $ bundle add python_uml_class

If bundler is not being used to manage dependencies, install the gem by executing:

    $ gem install python_uml_class

## Usage

    $ start_python_uml_class.rb

![class](img/class.png)

## Release Notes

### v0.2.1
- **Feature**: Added `python_path` setting in `setting.json` to allow specifying a custom Python path when executing the formatter script.
- **Feature**: Added `class_color` and `color_class_name` settings in `setting.json`. Classes matching the `color_class_name` regular expression will be displayed with the specified `class_color` along with their inheritance (`-|>`) and composition (`*--`) relationship lines.
- **Enhancement**: Improved the extraction of class compositions to properly detect class instantiations inside parentheses (e.g., `chat_history.append(HumanMessage(content=...))`).
- **Enhancement**: Modified class extraction to output fully qualified module names (e.g., `langchain_core.messages.HumanMessage`) when an alias or module path is specified via `from module import Class` or `import module as alias`.
- **Enhancement**: Filtered the extracted objects to include only the classes explicitly imported or defined locally within the parsed file.
- **Bug Fix**: Addressed an issue where variables defined with `class_` prefix (like `class_var`) or variables without assignments but containing type hints (like `global_var: int`) were incorrectly identified.
- **Bug Fix**: Fixed a bug where multi-line strings (`"""` or `'''`) or empty lines containing whitespace only within class functions caused indentation miscalculations, leading to local variables being improperly recognized as class or global variables.

## Testing with Docker

You can use Docker to set up a development and testing environment for Ubuntu 22.04 and 24.04.

1. Move to `test/docker/ubuntu`.
    ```bash
    $ cd test/docker/ubuntu
    ```

2. Build and start the container using docker compose.
   - For Ubuntu 22.04:
     ```bash
     $ docker compose up -d --build
     ```
   - For Ubuntu 24.04:
     ```bash
     $ docker compose -f docker-compose-24.04.yml up -d --build
     ```

3. Log in to the container to run tests or the application. (The source code is mounted at `/work` inside the container)
   - For Ubuntu 22.04:
     ```bash
     $ docker exec -it ubuntu bash
     ```
   - For Ubuntu 24.04:
     ```bash
     $ docker exec -it ubuntu-24.04 bash
     ```

4. Run tests inside the container.
    ```bash
    $ cd /work
    $ bundle install
    $ bundle exec rspec
    ```

## Development

To install this gem onto your local machine, run `bundle exec rake install`. To release a new version, update the version number in `version.rb`, and then run `bundle exec rake release`, which will create a git tag for the version, push git commits and the created tag, and push the `.gem` file to [pythongems.org](https://pythongems.org).

## Contributing

Bug reports and pull requests are welcome on GitHub at https://github.com/kuwayama1971/PythonUmlClass.

## License

The gem is available as open source under the terms of the [MIT License](https://opensource.org/licenses/MIT).