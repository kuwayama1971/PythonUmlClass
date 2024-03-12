require "tempfile"
require "facter"

CStruct = Struct.new(:type,
                     :file_name,
                     :name,
                     :block_count,
                     :var_list,
                     :method_list,
                     :inherit_list,
                     :composition_list)

def get_formatter_path
  return @config["formatter_path"] if @config["formatter_path"].to_s != ""

  ""
end

def print_uml(out, out_list)
  out_list.each do |o_list|
    if o_list.type == :class_start
      # nop
    elsif o_list.type == :module_start
      out.push "namespace \"#{o_list.name}\" {"
    elsif o_list.type == :class_end
      pp o_list if o_list.name == ""
      out.push "class \"#{o_list.name}\" {"
      # インスタンス変数の出力
      o_list.var_list.uniq.each do |iv|
        out.push iv
      end
      # メソッドの出力
      o_list.method_list.each do |ml|
        out.push ml
      end
      out.push "}"
      # 継承リストの出力
      o_list.inherit_list.each do |ih|
        out.push "\"#{o_list.name}\" -[##{@config["inherit_color"]}]-|> \"#{ih}\""
      end
      # compo
      o_list.composition_list.uniq.each do |co|
        out.push "\"#{o_list.name}\" *-[##{@config["composition_color"]}]- \"#{co}\""
      end
    elsif o_list.type == :module_end
      # インスタンス変数がある場合はモジュール名と同じクラスを定義
      if o_list.var_list.size != 0 or
         o_list.method_list.size != 0 or
         o_list.inherit_list.size != 0 or
         o_list.composition_list.size != 0
        pp o_list if o_list.name == ""
        out.push "class #{o_list.name} {"
        # インスタンス変数の出力
        o_list.var_list.uniq.each do |iv|
          out.push iv
        end
        # メソッドの出力
        o_list.method_list.each do |ml|
          out.push ml
        end
        out.push "}"
        # 継承リストの出力
        o_list.inherit_list.each do |ih|
          out.push "\"#{o_list.name}\" -[##{@config["inherit_color"]}]-|> \"#{ih}\""
        end
        # compo
        o_list.composition_list.uniq.each do |co|
          out.push "\"#{o_list.name}\" *-[##{@config["composition_color"]}]- \"#{co}\""
        end
      end
      out.push "}"
    else
      # error
      puts "error!"
    end
  end
  out
end

def create_uml_class(in_dir, _out_file)
  out = []
  out.push "@startuml"

  puts "in_dir = #{in_dir}"
  global_var = []
  out_list = []
  def_list = []
  import_list = []

  Dir.glob("#{in_dir}/**/*.py") do |f|
    import_list.push File.basename(f).split(".")[0]
  end

  Dir.glob("#{in_dir}/**/*.py") do |f|
    puts f
    puts @config["exclude_path"]
    if @config["exclude_path"] != ""
      if f =~ Regexp.new(@config["exclude_path"])
        puts "skip #{f}"
        next
      end
    end
    buf = ""
    file_name = File.basename(f).split(".")[0]
    Tempfile.create("pylint") do |tmp_file|
      # FileUtils.cp(f, tmp_file.path)
      kernel = Facter.value(:kernel)
      if kernel == "windows"
        open("|#{get_formatter_path} #{f} > #{tmp_file.path}") do |ff|
          if ff.read.to_s != ""
            puts "pylint error #{ff}"
            return
          else
            buf = File.binread tmp_file.path
          end
        end
      else
        open("|#{get_formatter_path} #{f} > #{tmp_file.path}") do |ff|
          puts "|#{get_formatter_path} #{f} > #{tmp_file.path}"
          if ff.read.to_s != ""
            puts "pylint error #{ff}"
            return
          else
            buf = File.binread tmp_file.path
          end
        end
      end
    end

    cstruct_list = []
    block_count = 0
    method_type = :public
    class_name = ""
    file_struct_list = []
    file_struct_list.push CStruct.new(:class_start, file_name, file_name + ".global", block_count, [], [], [], [])
    file_struct_list.push CStruct.new(:class_end, file_name, file_name + ".global", block_count, [], [], [], [])
    is_def = false

    # ソースを解析
    buf.each_line do |line|
      next if line =~ /^[\r\n]*$/ # 空行は対象外

      line.chomp!
      # ブロックの開始/終了
      indent_num = line.match(/^ +/).to_s.size / 4
      puts "block_count=#{indent_num} cstruct_size=#{cstruct_list.size} is_def=#{is_def} #{line}"
      if block_count == indent_num
        # 変化なし
      elsif block_count > indent_num
        # ブロックの終了
        block_count = indent_num
        # 関数の終了
        if is_def == true and def_list[-1].block_count >= block_count
          is_def = false
          method_type = :public
        end
        # クラスの終了
        if cstruct_list.size != 0 && cstruct_list[-1].block_count >= block_count # block_countが一致
          puts "end of #{cstruct_list[-1].name}"
          out_list.push cstruct_list[-1]
          cstruct_list.slice!(-1) # 最後の要素を削除
          method_type = :public
        end
      else
        # ブロックの開始
        block_count = indent_num
      end
      #puts "block_count=#{indent_num} class_count=#{cstruct_list.size} def_count=#{def_list.size} #{line}"

      # method_type
      if line =~ /@staticmethod/
        method_type = :private
      end

      # import
      line.match(/import \S+/) do |m|
        import_name = m.to_s.gsub(/import /, "")
        if 0 != import_list.select { |im| im == import_name }.size and file_name != import_name
          if cstruct_list.size != 0
            cstruct_list[-1].composition_list.push import_name
          else
            file_struct_list[-1].composition_list.push import_name
          end
        end
      end

      # クラスの開始
      if line =~ /^\s*class.*:/
        work = line.gsub(/class\s/, "")
        class_name = work.split("\(")[0].to_s.gsub(/:/, "")
        base_name = work.match(/\(.*\)/).to_s.gsub(/[()]/, "")
        class_name = "#{file_name}.#{class_name}"
        puts "class_name=#{class_name}"
        puts "base_name=#{base_name}"
        out_list.push CStruct.new(:class_start, file_name, class_name, block_count, [], [], [], [])
        cstruct_list.push CStruct.new(:class_end, file_name, class_name, block_count, [], [], [], [])
        # pp line if class_name == ""
        if base_name != ""
          if base_name =~ /,/
            base_name.split(",").each do |name|
              cstruct_list[-1].inherit_list.push name
            end
          else
            cstruct_list[-1].inherit_list.push base_name
          end
        end
        next
      end

      if line =~ /^\s*private$/
        method_type = :private
      elsif line =~ /^\s*protected$/
        method_type = :protected
      elsif line =~ /^\s*public$/
        method_type = :public
      end

      if line =~ /^\s*def\s/
        # 関数名を取り出す
        method = line.chomp.gsub(/\s*def\s*/, "")
        unless method =~ /\(/
          # 関数名にカッコをつける
          sp = method.split(" ")
          method = if sp.size > 1
              sp[0].to_s + "(" + sp[1..-1].to_s + ")"
            else
              method + "()"
            end
        end
        if cstruct_list.size != 0
          method_list = cstruct_list[-1].method_list
          case method_type
          when :public
            method_list.push "+ #{method}"
          when :private
            method_list.push "- #{method}"
          when :protected
            method_list.push "# #{method}"
          end
        else
          method_list = file_struct_list[-1].method_list
          method_list.push "+ #{method}"
        end
        def_list.push CStruct.new(:method_start, file_name, method, block_count, [], [], [], [])
        is_def = true
      end

      # composition_list
      # クラスの呼び出し箇所
      line.match(/\s([A-Z][a-zA-Z]+)\.[a-z]/) do |m|
        c_name = m.to_s.split(".")[0].gsub(/ /, "")
        puts "compo c_name=#{c_name}"
        if cstruct_list.size != 0
          cstruct_list[-1].composition_list.push c_name
        else
          file_struct_list[-1].composition_list.push c_name
        end
      end

      # クラスの初期化箇所
      line.match(/[\s\.][A-Z][A-Za-z]+\(/) do |m|
        c_name = m.to_s.gsub(/\(/, "").gsub(/[\s\.]/, "")
        puts "compo c_name=#{c_name}"
        if cstruct_list.size != 0
          cstruct_list[-1].composition_list.push c_name
        else
          file_struct_list[-1].composition_list.push c_name
        end
      end

      # インスタンス変数
      if line =~ /^\s*self\.[a-zA-Z0-9_]+\s+=/ and cstruct_list.size != 0
        line.match(/self\.[a-zA-Z0-9_]+/) do |m|
          instance_var = cstruct_list[-1].var_list
          val = m.to_s.gsub(/self\./, "")
          case method_type
          when :public
            instance_var.push "+ #{val}"
          when :private
            instance_var.push "- #{val}"
          when :protected
            instance_var.push "# #{val}"
          end
        end
      end

      # クラス変数
      if line =~ /^\s*[a-zA-Z0-9_]+\s+=/ and cstruct_list.size != 0 and is_def == false
        line.match(/[a-zA-Z0-9_]+/) do |m|
          instance_var = cstruct_list[-1].var_list
          val = m.to_s
          instance_var.push "- #{val}"
        end
      end

      # 外部変数
      if line =~ /^\s*[a-zA-Z0-9_]+\s+=/ and cstruct_list.size == 0 and is_def == false
        line.match(/\$*[a-zA-Z0-9_]+/) do |m|
          file_struct_list[-1].var_list.push "+ #{m}"
        end
      end
    end

    # ファイルの終了
    if block_count != 0
      puts "endf of  #{f}"
      # クラスの終了
      if cstruct_list.size != 0
        puts "end of #{cstruct_list[-1].name}"
        out_list.push cstruct_list[-1]
        cstruct_list.slice!(-1) # 最後の要素を削除
      end
      file_struct_list.each do |fs|
        out_list.push fs
      end
    end
  end

  # 継承リストとコンポジションリストのチュエック
  out_list.each_index do |i|
    out_list[i].composition_list.each_index do |j|
      # compo_nameがfile_name.class_nameに変更可能かチェック
      compo_name = out_list[i].composition_list[j]
      out_list.select { |a| a.name.split(".")[-1] == compo_name }.each do |m|
        puts "m=#{m.name}"
        out_list[i].composition_list[j] = m.name
      end
      def_list.each do |def_struct|
        # comp_nameが自分で定義した関数名の場合は削除
        #puts "#{compo_name} == #{def_struct.name.split("(")[0]}"
        if compo_name == def_struct.name.split("(")[0]
          puts "match_def #{compo_name} == #{def_struct.name.split("(")[0]}"
          out_list[i].composition_list.delete_at(j)
        end
      end
    end
    out_list[i].inherit_list.each_index do |j|
      # compo_nameがfile_name.class_nameに変更可能かチェック
      inherit_name = out_list[i].inherit_list[j]
      out_list.select { |a| a.name.split(".")[-1] == inherit_name }.each do |m|
        puts "m=#{m.name}"
        out_list[i].inherit_list[j] = m.name
      end
    end
  end

  # UMLの出力
  out = print_uml(out, out_list)

  out.push "@enduml"
  out.join("\n")
end
