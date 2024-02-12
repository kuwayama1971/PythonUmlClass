require "./server_app_base"
require "json"
require "cgi"
require "thread"

def config_json_hash(json)
  config = {}
  json["setting_list"].each do |j|
    config[j["name"]] = j["value"]
  end
  return config
end

$ws_exit_thread = nil

class WsServer < Sinatra::Base
  def initialize
    super
    @ws_list = []
    @ws_lock = Mutex.new
  end

  def ws_send(str)
    @ws_lock.synchronize do
      if @ws_list[0] != nil
        @ws_list[0].send(str)
      end
    end
  end

  json_config = nil
  exec_thread = nil
  get "" do
    if !request.websocket?
      "no supported"
    else
      request.websocket do |ws|
        ws.onopen do
          puts "ws.open"
          @ws_lock.synchronize do
            @ws_list << ws
            $app.set_ws(ws)
            pp "ws=#{ws}"
          end
          ws_send("startup:#{$startup_file}")
          puts "ws_exit_thread=#{$ws_exit_thread}"
          if $ws_exit_thread != nil
            puts "ws_exit_thread kill"
            Thread.kill $ws_exit_thread
          end
        end
        ws.onmessage do |msg|
          puts msg
          json = JSON.parse(File.read("#{$home_dir}/config/setting.json"))
          json_config = config_json_hash(json)
          $app.set_config(json_config)
          if msg =~ /^exec:/
            if exec_thread == nil
              argv = msg.gsub(/^exec:/, "")
              exec_thread = Thread.new {
                begin
                  $app.start(argv.split(",")) do |out|
                    ws_send(out)
                  end
                  ws_send("app_end:normal")
                rescue
                  puts $!
                  puts $@
                  puts "app_end:err"
                  ws_send("app_end:error")
                ensure
                  puts "exit thread"
                  exec_thread = nil
                end
              }
            else
              puts "app_end:err"
              ws_send("app_end:error")
            end
          end
          if msg =~ /^stop/
            if exec_thread
              Thread.kill exec_thread
              ws_send("app_end:stop")
              $app.stop
            end
          end
          if msg =~ /^suspend/
            if exec_thread
              $app.suspend
            end
          end
          if msg =~ /^resume/
            if exec_thread
              $app.resume
            end
          end
          if msg =~ /^setting:/
            json_string = msg.gsub(/^setting:/, "")
            begin
              json = JSON.parse(json_string)
              File.open("#{$home_dir}/config/setting.json", "w") do |w|
                w.puts JSON.pretty_generate(json)
              end
              json_config = config_json_hash(json)
              $app.set_config(json_config)
            rescue
              # jsonファイルではない
              ws_send("app_end:error")
            end
          end
          if msg =~ /^openfile:/
            file = msg.gsub(/^openfile:/, "")
            if file != ""
              Thread.new {
                system "#{json_config["editor"]} #{CGI.unescapeHTML(file)}"
              }
            end
          end

          # アプリケーション終了
          if msg == "exit"
            #halt
            exit
          end
        end

        # close websocket
        ws.onclose do
          puts "websocket closed"
          @ws_lock.synchronize do
            @ws_list.delete(ws)
          end
          puts @ws_list.size
          if @ws_list.size == 0
            $ws_exit_thread = Thread.start {
              sleep 1
              #halt
              exit
            }
            puts "ws_exit_thread=#{$ws_exit_thread}"
          end
        end
      end
    end
  end
end
