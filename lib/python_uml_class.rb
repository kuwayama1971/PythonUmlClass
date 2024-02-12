# -*- coding: utf-8 -*-
require "server_app_base.rb"
require "kconv"
#require "create_uml_class.rb"

class PythonUmlClass < AppMainBase
  def start(argv)
    super
    begin
      @abort = false
      puts argv
      in_dir = argv[0]
      out_file = argv[1]

      # 履歴の保存
      add_history("history.json", in_dir)
      add_history("out_history.json", out_file)

      # Browserにメッセージ送信
      #app_send("popup:start app #{argv[0]}")

      out_svg = out_file.gsub(File.extname(out_file), "") + ".svg"

      # uml作成
      load "create_uml_class.rb"

      uml = create_uml_class(in_dir, out_file)

      File.open(out_file, "w") do |f|
        f.puts uml
      end

      # PlantUMLの実行
      FileUtils.rm_f out_svg
      cmd = "#{@config["plantuml"]} #{out_file}"
      puts cmd
      system cmd
      if File.exist? out_svg
        yield File.read out_svg
      else
        yield "exec error"
        yield cmd
      end
    rescue
      puts $!
      puts $@
      yield $!.to_s.toutf8
      yield $@.to_s.toutf8
    end
  end

  def stop()
    super
  end
end
