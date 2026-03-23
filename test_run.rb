require_relative 'lib/create_uml_class'
@config = {
  "python_path" => "python3",
  "formatter_path" => "lib/del_comment.py",
  "exclude_path" => ""
}
uml = create_uml_class('.', 'out.pu')
