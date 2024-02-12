# -*- coding: utf-8 -*-
require "server_app_base.rb"

class MyApp < AppMainBase
  def start(argv)
    super
    begin
      @abort = false
      puts argv
      argv.each do |v|
        yield v if block_given?
      end

      # Browserにメッセージ送信
      app_send("popup:start app #{argv[0]}")

      # 履歴の保存
      add_history("history.json", argv[0])

      while true
        yield Time.now.to_s if block_given?
        puts Time.now.to_s
        yield @config["name1"]
        sleep 1
        break if @abort
      end
    rescue
      puts $!
      puts $@
    end
  end

  def stop()
    super
  end
end
