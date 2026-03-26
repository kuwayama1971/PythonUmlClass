#!/usr/bin/env ruby
# -*- coding: utf-8 -*-
$LOAD_PATH << File.dirname(File.expand_path(__FILE__))

require 'rubygems'
require 'rubygems'

begin
  require 'bundler/setup'
rescue LoadError
  gem 'rack'
  gem 'rackup'
end

require 'rack'
begin
  require 'rackup'
  require 'rackup/server'
rescue LoadError
  # Fallback to older rack
  require 'rack/server'
  Object.const_set("Rackup", Rack) unless defined?(Rackup)
end

require 'bundler/setup'
require "socket"
require "daemons"
require "fileutils"
require "kconv"
require "json"
require "facter"

# ログ出力
module Output
  def self.console_and_file(output_file, stdout = true)
    begin
      defout = File.new(output_file, "a+")
    rescue
      puts $!
      puts $@
      return nil
    end
    class << defout
      alias_method :write_org, :write

      def initialize(stdout)
        @stdout = false
      end

      attr_accessor :stdout

      def puts(str)
        STDOUT.write(str.to_s + "\n") if @stdout
        self.write_org(str.to_s + "\n")
        self.flush
      end

      def write(str)
        STDOUT.write(str) if @stdout
        self.write_org(str)
        self.flush
      end
    end
    $stdout = defout
    $stdout.stdout = stdout
  end
end

# ディレクトリ移動
dir = File.dirname(File.expand_path(__FILE__))
FileUtils.cd dir

# ディレクトリ作成
pp ARGV
if ARGV[0] == "test"
  $home_dir = "./"
  ARGV = []
else
  $home_dir = ENV["HOME"] + "/" + dir.split("/")[-1].gsub(/-[0-9\.-]+/,"") + "/"
end
puts "home_dir=#{$home_dir}"
FileUtils.mkdir_p("#{$home_dir}/logs")
FileUtils.mkdir_p("#{$home_dir}/history")
Output.console_and_file("#{$home_dir}/logs/app.log", true)

# 空きポートを取得
def get_unused_port
  s = TCPServer.open(0)
  port = s.addr[1]
  s.close
  return port
end

# 空きポートを取得
port = get_unused_port
puts "port=#{port}"

# config.ruの編集は不要 (Rackup/Server optionsでポートを指定する)

# main.jsの編集
buf = File.binread("js/main.js").toutf8
buf.gsub!(/localhost:[0-9]+\//, "localhost:#{port}/")
buf.gsub!(/localhost:[0-9]+\/wsserver/, "localhost:#{port}/wsserver")
# ws://localhost:12345/wsserver のようなパターンの置換をより確実に行う
buf.gsub!(/ws:\/\/localhost:[0-9]+\/wsserver/, "ws://localhost:#{port}/wsserver")
File.binwrite("js/main.js", buf)

# html/index.htmlの編集
buf = File.binread("html/index.html").toutf8
buf.gsub!(/localhost:[0-9]+\//, "localhost:#{port}/")
File.binwrite("html/index.html", buf)

begin
  Thread.start {
    puts "wait start web server"
    while true
      begin
        s = TCPSocket.open("localhost", port)
        s.close
        break
      rescue
        puts $!
        sleep 0.1
      end
    end

    puts "start browser"
    json_file = "#{$home_dir}/config/browser.json"
    json = JSON.parse(File.read json_file)
    puts json
    kernel = Facter.value(:kernel)
    if kernel == "windows"
      browser = json["chrome_win"]
    elsif kernel == "Linux"
      browser = json["chrome_linux"]
    else
      browser = json["chrome_win"]
    end
    browser += " -app=http://localhost:#{port}"
    puts browser
    system browser
  }

  # start web server
  server_class = defined?(Rackup::Server) ? Rackup::Server : Rack::Server
  server_class.start(:Port => port, :config => "config.ru", :server => 'thin')
rescue
  puts $!
  puts $@
  exit
end
