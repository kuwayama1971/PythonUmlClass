# frozen_string_literal: true

require "spec_helper"
require_relative "../lib/create_uml_class"
require "fileutils"
require "tmpdir"

RSpec.describe "Variables extraction" do
  before do
    @config = {
      "python_path" => "python",
      "formatter_path" => "dummy_formatter.py",
      "exclude_path" => ""
    }
  end

  it "extracts class and global variables" do
    Dir.mktmpdir do |dir|
      File.write(File.join(dir, "sample.py"), <<~PYTHON)
        global_var1 = 1
        global_var2: int = 2
        global_var3: int

        class MyClass:
            class_var1 = 1
            class_var2: int = 2
            class_var3: int

            def my_method(self):
                local_var = 3
    # A comment at class level indent
                local_var_after_comment = 5
                self.instance_var = 4
      PYTHON

      allow(Facter).to receive(:value).with(:kernel).and_return("linux")
      allow(self).to receive(:open).and_yield(StringIO.new(""))
      allow(File).to receive(:binread).and_return(File.read(File.join(dir, "sample.py")))

      uml = create_uml_class(dir, "out.puml")
      expect(uml).to include("- class_var1")
      expect(uml).to include("- class_var2")
      expect(uml).to include("- class_var3")
      expect(uml).to include("+ global_var1")
      expect(uml).to include("+ global_var2")
      expect(uml).to include("+ global_var3")
      expect(uml).not_to include("local_var")
      expect(uml).not_to include("local_var_after_comment")
    end
  end

  it "ignores multi-line strings for indentation tracking" do
    Dir.mktmpdir do |dir|
      File.write(File.join(dir, "sample.py"), <<~PYTHON)
        class SaveProductTool:
            def _run(self):
                email_body = f"""Action: Saved

        Name: {name}
        Store: {store}
        """
                rows_parsed = []
      PYTHON

      allow(Facter).to receive(:value).with(:kernel).and_return("linux")
      allow(self).to receive(:open).and_yield(StringIO.new(""))
      allow(File).to receive(:binread).and_return(File.read(File.join(dir, "sample.py")))

      uml = create_uml_class(dir, "out.puml")
      # rows_parsed should NOT be extracted as a global or class variable
      expect(uml).not_to include("rows_parsed")
    end
  end
end
