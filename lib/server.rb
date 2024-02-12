require "json"
require "kconv"

class Search < Sinatra::Base
  helpers Sinatra::Streaming
  get "" do
    q_hash = {}
    puts request.query_string
    request.query_string.split("&").each do |q|
      work = q.split("=")
      if work[1] != nil
        q_hash[work[0]] = CGI.unescape work[1].toutf8
      else
        q_hash[work[0]] = ""
      end
    end
    str = q_hash["path"].gsub(/\\/, "/")
    puts "str=#{str}"
    kind = q_hash["kind"].gsub(/\\/, "/")
    puts "kind=#{kind}"
    res = []
    str = str.gsub(/\\/, "/")
    dir = File.dirname(str)
    file = File.basename(str)
    puts "dir=#{dir}"
    puts "file=#{file}"

    kernel = Facter.value(:kernel)
    if kernel == "windows"
      dir = "c:/" if dir == nil
      dir = "c:/" if dir == "/"
    elsif kernel == "Linux"
      dir = "/" if dir == nil
    else
      dir = "c:/" if dir == nil
      dir = "c:/" if dir == "/"
    end

    path = "#{dir}/#{file}"
    if File.directory?(path)
      path = path + "/*"
    else
      path = path + "*"
    end
    path.gsub!(/[\/]+/, "/")
    puts path
    Dir.glob(path, File::FNM_DOTMATCH).each do |file|
      data = {}
      next if File.basename(file) == "."
      next if kind == "dir" and !File.directory?(file)
      data["label"] = File.basename(file)
      data["label"] += "/" if (File.directory?(file))
      data["value"] = File.expand_path(file)
      res.push data
    end
    JSON.generate res.sort { |a, b| a["value"] <=> b["value"] }
  end
end
