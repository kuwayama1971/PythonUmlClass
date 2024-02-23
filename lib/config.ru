# -*- coding: utf-8 -*-
require "sinatra"
require "sinatra/contrib"
require "sinatra-websocket"
require "thin"
require "json"

require "./server"
require "./wsserver"

access_log = File.new("#{$home_dir}/logs/sinatra.log", "a+")
access_log.sync = true
use Rack::CommonLogger, access_log

get "/" do
  File.read("html/index.html")
end

get "*.html" do |file|
  content_type "text/html", :charset => "utf-8"
  File.read "./html/#{file}.html"
end

get "/css/:name.css" do
  content_type "text/css", :charset => "utf-8"
  puts "css/#{params[:name]}.css"
  File.read "css/#{params[:name]}.css"
end

get "/js/:name.js" do
  content_type "text/javascript", :charset => "utf-8"
  puts "js/#{params[:name]}.js"
  File.read "js/#{params[:name]}.js"
end

get "/config/*.*" do |file, ext|
  content_type "text/json", :charset => "utf-8"
  puts "#{file}.#{ext}"
  File.read "#{$home_dir}/config/#{file}.#{ext}"
end

post "/history/*.*" do |file, ext|
  content_type "text/json", :charset => "utf-8"
  puts "#{file}.#{ext}"
  p = params[:param1]
  begin
    buf = File.read "#{$home_dir}/history/#{file}.#{ext}"
  rescue
    buf = ""
  end
  data = eval(buf)
  if data != nil
    if p != ""
      JSON.generate data.find_all { |d| d =~ Regexp.new(p) }
    else
      JSON.generate data
    end
  end
end

get "/open_dialog" do
  dialog_html = <<'EOS'
  <!DOCTYPE html>
  <html>
  <head>
    <meta http-equiv="Content-Type" content="text/html; charset=utf-8" />
    <title>Message Dialog</title>
    <style type="text/css">
    <!--
    body {
      color: #000000;
      background-color: #ffffff;
      overflow: hidden;
      font-size: 12px;
    }
    -->    
    </style>
    </head>
EOS
  dialog_html += "<body>" + params["msg"] + "</body></html>"
end

map "/search" do
  run Search
end

map "/wsserver" do
  res = catch(:halt) do
    run WsServer
  end
  puts res
end

configure do
  set :DoNotReverseLookup, true
  set :logging, true
  set :default_encoding, "utf-8"
  set :server, :thin

  #  Thread.start {
  #  }

end

#\ --port 37583

run Sinatra::Application
