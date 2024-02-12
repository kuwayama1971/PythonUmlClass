# -*- coding: utf-8 -*-
class AppMainBase
  def initialize
    @config = nil
    @aboet = false
    @exec = false
    @suspend = false
    @ws = nil
  end

  def app_send(str)
    if @ws != nil
      @ws.send(str)
    end
  end

  def set_ws(ws)
    @ws = ws
  end

  def set_config(config)
    @config = config
  end

  def start(argv)
    @exec = true
  end

  def stop()
    @abort = true
    @exec = false
  end

  def suspend()
    @suspend = true
  end

  def resume()
    @suspend = false
  end

  # 履歴の保存
  def add_history(file, history_data, max = 10)
    begin
      buf = File.read "#{$home_dir}history/#{file}"
    rescue
      buf = ""
    end
    data = eval(buf)
    if data == nil
      data = []
    end
    if history_data.to_s != ""
      data.prepend history_data
    end
    data = data.uniq[0..max - 1]
    File.open("#{$home_dir}history/#{file}", "w") do |f|
      f.write JSON.pretty_generate data
    end
  end
end

require "app_load.rb"
