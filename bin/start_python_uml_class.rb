#!/usr/bin/env ruby

require "fileutils"
require "facter"
require "tmpdir"
require "json"

# tmpdirディレクトリにコピー
dir = File.dirname(File.expand_path(__FILE__ + "/../"))
home_dir = ENV["HOME"] + "/" + dir.split("/")[-1].gsub(/-[0-9\.-]+/,"")
puts "home_dir=#{home_dir}"
Dir.mktmpdir { |tmpdir|
  outdir = tmpdir + "/" + dir.split("/")[-1]
  FileUtils.mkdir_p outdir
  FileUtils.mkdir_p home_dir
  puts outdir
  Dir.glob("#{dir}/lib/*") do |f|
    if f =~ /config$/
      # configはhomeにコピー
      if !File.exists? "#{home_dir}/config"
        puts "#{f} => #{home_dir}/"
        FileUtils.cp_r f, "#{home_dir}/"
      end
    else
      puts "#{f} => #{outdir}/"
      FileUtils.cp_r f, "#{outdir}/"
    end
  end
  begin
  json = JSON.parse(File.read("#{home_dir}/config/setting.json"))
  old_version = json["version"]
  rescue
    old_version = ""
  end
  json = JSON.parse(File.read("#{dir}/lib/config/setting.json"))
  new_version = json["version"]
  puts "#{old_version} == #{new_version}"
  if old_version.to_s != new_version.to_s
    FileUtils.cp "#{dir}/lib/config/setting.json", "#{home_dir}/config/setting.json"
  end

  FileUtils.cd "#{outdir}"
  kernel = Facter.value(:kernel)
  if kernel == "windows"
    system "rubyw ./start.rb"
  elsif kernel == "Linux"
    system "ruby ./start.rb"
  else
    system "ruby ./start.rb"
  end
  FileUtils.cd ENV["HOME"]
}
