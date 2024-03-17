# frozen_string_literal: true

require_relative "lib/python_uml_class/version"

Gem::Specification.new do |spec|
  spec.name = "python_uml_class"
  spec.version = PythonUmlClassVer::VERSION
  spec.authors = ["Masataka kuwayama"]
  spec.email = ["masataka.kuwayama@gmail.com"]

  spec.summary = "Create a Python UML class diagram."
  spec.description = "Create a Python UML class diagram with PlangUml."
  spec.homepage = "https://github.com/kuwayama1971/PythonUmlClass"
  spec.license = "MIT"
  spec.required_ruby_version = ">= 2.6.0"

  spec.metadata["allowed_push_host"] = "https://rubygems.org"

  spec.metadata["homepage_uri"] = spec.homepage
  spec.metadata["source_code_uri"] = spec.homepage
  spec.metadata["changelog_uri"] = spec.homepage

  # Specify which files should be added to the gem when it is released.
  # The `git ls-files -z` loads the files in the RubyGem that have been added into git.
  spec.files = Dir.chdir(__dir__) do
    `git ls-files -z`.split("\x0").reject do |f|
      (f == __FILE__) || f.match(%r{\A(?:(?:test|spec|features)/|\.(?:git|travis|circleci)|appveyor)})
    end
  end
  spec.bindir = "bin"
  spec.executables = spec.files.grep(%r{^bin/}) { |f| File.basename(f) }
  spec.require_paths = ["lib"]

  # Uncomment to register a new dependency of your gem
  # spec.add_dependency "example-gem", "~> 1.0"

  spec.add_dependency "browser_app_base", "~> 0.1"
  spec.add_dependency "facter", "~> 4.2"
  #spec.add_dependency "rufo", "~> 0.1"

  # For more information and examples about making a new gem, check out our
  # guide at: https://bundler.io/guides/creating_gem.html
end
