# PythonUmlClass
Pythonのクラス図を作成します。

他の言語で読む: [English](README.md), [日本語](README_JA.md)

## セットアップ
    Ubuntuの場合
    $ sudo apt install plantuml
    $ sudo apt install python3.12-venv
    $ python3 -m venv .venv
    $ source .venv/bin/activate
    $ pip install astor

    Google Chromeのインストール
    $ echo "deb http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google.list
    $ wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add -
    $ apt update
    $ apt -y install google-chrome-stable

## インストール

アプリケーションのGemfileに以下を追加してインストールします:

    $ bundle add python_uml_class

bundlerを使用していない場合は、以下のコマンドでgemをインストールします:

    $ gem install python_uml_class

## 使用方法

    $ start_python_uml_class.rb

![class](img/class.png)

## リリースノート

### v0.2.1
- **機能追加**: `setting.json` に `python_path` 設定を追加し、フォーマッターのスクリプトを実行する際の Python のパスを指定可能にしました。
- **機能追加**: `setting.json` に `class_color` と `color_class_name` 設定を追加。`color_class_name` の正規表現に部分一致するクラスは、PlantUML出力時にクラス自体の背景色と、そのクラスへ繋がる継承 (`-|>`) やコンポジション (`*--`) の矢印線の色が `class_color` で指定した色になります。
- **改善**: コンポジション関係の抽出処理（クラスの初期化）を強化し、括弧内の呼び出し（例: `chat_history.append(HumanMessage(content=...))`）であってもクラスのインスタンス化を正しく検出できるようにしました。
- **改善**: `from ... import ...` や `import ... as ...` などでインポートされたクラスを利用する際、元の完全修飾名（例: `langchain_core.messages.HumanMessage`）を復元してUMLに正しく出力するように修正しました。
- **改善**: クラスの初期化（コンポジション）において、同じファイル内で定義されたクラスか、明示的にインポートされたクラスのみを対象とするようにフィルタリング処理を強化しました。
- **バグ修正**: `class_var` のように名前に `class` を含む変数が誤ってクラス宣言として認識される問題や、型ヒントのみ（`global_var: int` など）で代入を伴わないクラス変数・外部変数が正しく抽出されない問題を修正しました。
- **バグ修正**: クラス内の関数（メソッド）に空白のみの空行や、マルチライン文字列（`"""` や `'''`）が含まれる場合、インデントレベルが誤認されて以降のローカル変数が「クラス変数」や「外部変数（グローバル）」として誤って抽出・出力されるバグを修正しました。

## Dockerでのテスト環境構築

Dockerを使用して開発・テスト環境（Ubuntu 22.04、および24.04）を構築できます。

1. `test/docker/ubuntu` に移動します。
    ```bash
    $ cd test/docker/ubuntu
    ```

2. docker composeを使用してコンテナをビルド・起動します。
   - Ubuntu 22.04 の場合:
     ```bash
     $ docker compose up -d --build
     ```
   - Ubuntu 24.04 の場合:
     ```bash
     $ docker compose -f docker-compose-24.04.yml up -d --build
     ```

3. コンテナにログインしてテストやアプリケーションの実行を行います。（ソースコードはコンテナ内の `/work` にマウントされています）
   - Ubuntu 22.04 の場合:
     ```bash
     $ docker exec -it ubuntu bash
     ```
   - Ubuntu 24.04 の場合:
     ```bash
     $ docker exec -it ubuntu-24.04 bash
     ```

4. コンテナ内でテストを実行します。
    ```bash
    $ cd /work
    $ bundle install
    $ bundle exec rspec
    ```

## 開発

このgemをローカルマシンにインストールするには、`bundle exec rake install`を実行します。新しいバージョンをリリースするには、`version.rb`のバージョン番号を更新してから、`bundle exec rake release`を実行します。これにより、バージョンのgitタグが作成され、コミットとタグがプッシュされ、`.gem`ファイルが[pythongems.org](https://pythongems.org)にプッシュされます。

## コントリビューション

バグレポートとプルリクエストはGitHub https://github.com/kuwayama1971/PythonUmlClass で歓迎します。

## ライセンス

このgemは[MIT License](https://opensource.org/licenses/MIT)の条件の下でオープンソースとして利用可能です。