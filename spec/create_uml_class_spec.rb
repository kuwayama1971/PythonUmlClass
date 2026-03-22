# frozen_string_literal: true

require "spec_helper"
require_relative "../lib/create_uml_class"
require "fileutils"
require "tmpdir"

RSpec.describe "create_uml_class" do
  before do
    @config = {
      "python_path" => "python",
      "formatter_path" => "dummy_formatter.py",
      "exclude_path" => ""
    }
  end

  describe "#get_python_path" do
    it "returns the python_path from config if present" do
      expect(get_python_path).to eq("python")
    end

    it "returns 'python' if config is empty" do
      @config["python_path"] = ""
      expect(get_python_path).to eq("python")
    end
  end

  describe "#get_formatter_path" do
    it "returns the formatter_path from config if present" do
      expect(get_formatter_path).to eq("dummy_formatter.py")
    end

    it "returns empty string if config is empty" do
      @config["formatter_path"] = ""
      expect(get_formatter_path).to eq("")
    end
  end

  describe "#create_uml_class" do
    it "parses python files and returns UML string" do
      Dir.mktmpdir do |dir|
        File.write(File.join(dir, "sample.py"), <<~PYTHON)
          class MyClass:
              def my_method(self):
                  pass
        PYTHON

        # Mock Facter or system execution
        allow(Facter).to receive(:value).with(:kernel).and_return("linux")
        
        # We need to mock open to simulate the formatter execution
        allow(self).to receive(:open).and_yield(StringIO.new(""))
        allow(File).to receive(:binread).and_return(<<~PYTHON)
          class MyClass:
              def my_method(self):
                  pass
        PYTHON

        uml = create_uml_class(dir, "out.puml")
        
        expect(uml).to include("@startuml")
        expect(uml).to include("class \"sample.MyClass\" {")
        expect(uml).to include("+ my_method(self):")
        expect(uml).to include("@enduml")
      end
    end
  end
end
