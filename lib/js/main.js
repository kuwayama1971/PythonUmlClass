// main.js

var $ws = null;
var $auto_scroll = true;
var dialog = null;
var dialog_timeout = null;

function open_dialog(msg, timeout = 0) {
    console.log("msg=" + msg);
    $("#msg_text").html(msg);
    d = $("#msg_dialog").dialog({
        modal: true
        , show: "slide"         //表示時のアニメーション
        , hide: "slide"       //閉じた時のアニメーション
        , title: "Message"   //ダイアログのタイトル
        , width: 500            //ダイアログの横幅
        , height: 300           //ダイアログの高さ
        , resizable: true      //リサイズ可
        , closeOnEscape: false  //[ESC]キーで閉じられなくする
        , draggable: true      //ダイアログの移動を可に
        , buttons: {
            "OK": function () {  //Cancelボタン
                if (dialog_timeout != null) {
                    clearTimeout(dialog_timeout);
                }
                $(this).dialog("close");
            }
        }
    });
    if (timeout != 0) {
        dialog_timeout = setTimeout(function () {
            d.dialog("close");
        }, timeout);
    }
}

function open_dialog_org(msg) {
    var top = window.screenTop + 10;
    var left = window.screenLeft + 10;
    if (dialog != null) {
        dialog.close();
    }
    var dialog = window.open(
        "/open_dialog?msg=" + msg,
        "pop",
        "width=300, height=100, left=" + left + ", top=" + top
    );
    console.log("open dialog dialog=" + dialog);
    if (dialog == null) {
        console.log("open dialog retry");
        setTimeout(function () {
            open_dialog(msg);
        }, 1000);
    } else {
        dialog.focus();
    }
}

function server_connect(url) {
    var ws = new WebSocket(url);
    ws.onopen = function () {
        // Web Socket is connected. You can send data by send() method.
        ws.send("message to send");
    };
    ws.onmessage = function (evt) {
        //alert(evt.data);

        if (evt.data.match(/^startup:/)) {
            file_name = evt.data.replace(/^startup:/, "");
        }
        else if (evt.data.match(/^app_end:normal/)) {
            open_dialog("終了しました");
        }
        else if (evt.data.match(/^app_end:stop/)) {
            open_dialog("中止しました");
        }
        else if (evt.data.match(/^app_end:error/)) {
            open_dialog("<font color='red'>エラーが発生しました</font>");
        }
        else if (evt.data.match(/^popup:/)) {
            open_dialog(evt.data.replace(/^popup:/, ""), 3000);
        } else {
            var log = "<li>" + evt.data + "</li>";
            $('#log').append(log);
            if ($auto_scroll) {
                $('.outarea').scrollTop($('.outarea').get(0).scrollHeight);
            }
        }
    };
    ws.onclose = function () {
        alert("アプリケーションが終了しました!!");
        $(window).unbind("beforeunload");
        //window.open('about:blank','_self').close();
        window.close();
    };
    $ws = ws;
}

function send_message(msg) {
    if ($ws != null) {
        $ws.send(msg);
    }
}

function autocomp(id, file_kind) {
    $("#" + id).autocomplete({
        autoFocus: true,
        minLength: 0,
        delay: 0,
        select: function (event, ui) {
            //console.log(ui.item.value);
            jQuery("#" + id).val(ui.item.value);
            //jQuery(this).autocomplete("search", "");
            $(this).keydown();
        },
        source: function (req, resp) {
            $.ajax({
                url: "search?path=" + $("#" + id).val() + "&kind=" + file_kind,
                type: "GET",
                cache: false,
                dataType: "json",
                data: {
                    param1: req.term
                },
                success: function (o) {
                    resp(o);
                },
                error: function (xhr, ts, err) {
                    resp(['']);
                }
            });

        }
    }).focus(function () {
        //jQuery(this).autocomplete("search", "");
        $(this).keydown();
    });
}

function autocomp_history(id, file_name) {
    $("#" + id).autocomplete({
        autoFocus: true,
        minLength: 0,
        delay: 0,
        select: function (event, ui) {
            jQuery("#" + id).val(ui.item.value);
            $(this).keydown();
        },
        source: function (req, resp) {
            $.ajax({
                url: "history/" + file_name,
                type: "POST",
                cache: false,
                dataType: "json",
                data: {
                    param1: req.term
                },
                success: function (o) {
                    resp(o);
                },
                error: function (xhr, ts, err) {
                    resp(['']);
                }
            });

        }
    }).focus(function () {
        $(this).keydown();
    });
}

function select_file_dialog(search_id, file_kind, dialog_id, select_file, file_name) {
    $("#" + select_file).click(function () {
        autocomp(search_id, file_kind);
        $(".ui-autocomplete").css("z-index", 1000);
        console.log("name=" + $("#" + file_name).val());
        $("#" + search_id).val($("#" + file_name).val());
        $("#" + dialog_id).dialog({
            modal: true
            , show: "slide"         //表示時のアニメーション
            , hide: "explode"       //閉じた時のアニメーション
            , title: "Select File"   //ダイアログのタイトル
            , width: 580            //ダイアログの横幅
            , height: 400           //ダイアログの高さ
            , resizable: true      //リサイズ可
            , closeOnEscape: false  //[ESC]キーで閉じられなくする
            , draggable: true      //ダイアログの移動を可に
            , buttons: {
                "OK": function () {  //OKボタン
                    $("#" + file_name).val($("#" + search_id).val());
                    $(this).dialog("close");
                    $("#" + search_id).autocomplete("destroy");
                },
                "Cancel": function () {  //Cancelボタン
                    $(this).dialog("close");
                    $("#" + search_id).autocomplete("destroy");
                }
            }
        });
    });
}

function setting_dialog(open_id, dialog_id, json_file) {
    var version;
    $("#" + open_id).click(function () {
        $("#" + dialog_id).val = $(function () {
            $("dl#wrap").empty();
            $.getJSON(json_file, function (s) {
                version = s["version"];
                for (var i in s["setting_list"]) {
                    if (s["setting_list"][i].type == "input") {
                        var h = "<table><tr>"
                            + "<td class='setting_name'>" + s["setting_list"][i].description + "</td>"
                            + "<td><input class='setting_value' type='text' " + "id=" + s["setting_list"][i].name + "_value " + "value=" + "'" + s["setting_list"][i].value + "'" + ">"
                            + "</td></tr></table>"
                        $("dl#wrap").append(h);
                    } else if (s["setting_list"][i].type == "checkbox") {
                        var h = "<table><tr>";
                        h += "<td class='setting_name'>" + s["setting_list"][i].description + "</td>";
                        if (s["setting_list"][i].value == true) {
                            h += "<td><input class='setting_checkbox'  type='checkbox' " + "id=" + s["setting_list"][i].name + "_value checked ></td>";
                        } else {
                            h += "<td><input class='setting_checkbox'  type='checkbox' " + "id=" + s["setting_list"][i].name + "_value ></td>";
                        }
                        h += "</tr></table>";
                        $("dl#wrap").append(h);
                    } else if (s["setting_list"][i].type == "select") {
                        var h = "<table><tr>";
                        h += "<td class='setting_name'>" + s["setting_list"][i].description + "</td>";
                        h += "<td> <select class='setting_value'  id=" + s["setting_list"][i].name + "_value " + ">";
                        s["setting_list"][i].select.forEach(e => {
                            if (e == s["setting_list"][i].value) {
                                h += "<option value=" + e + " selected >" + e + "</option>";
                            } else {
                                h += "<option value=" + e + ">" + e + "</option>";
                            }
                        });
                        h += "</select></td>";
                        h += "</tr></table>";
                        $("dl#wrap").append(h);
                    } else {
                        //console.log("type=" + s["setting_list"][i].type);
                    }
                }
            });
        });
        $("#" + dialog_id).dialog({
            modal: true
            , show: "slide"         //表示時のアニメーション
            , hide: "explode"       //閉じた時のアニメーション
            , title: "Setting"   //ダイアログのタイトル
            , width: 580            //ダイアログの横幅
            , height: 400           //ダイアログの高さ
            , resizable: true      //リサイズ可
            , closeOnEscape: false  //[ESC]キーで閉じられなくする
            , draggable: true      //ダイアログの移動を可に
            , buttons: {
                "OK": function () {  //OKボタン
                    var json_obj = {};
                    var json_data = [];
                    $.getJSON(json_file, function (s) {
                        json_obj["version"] = s["version"];
                        for (var i in s["setting_list"]) {
                            //console.log(s["setting_list"][i].name);
                            if (s["setting_list"][i].type == "input") {
                                var data = {};
                                data["name"] = s["setting_list"][i].name;
                                data["value"] = $("#" + s["setting_list"][i].name + "_value").val();
                                data["type"] = s["setting_list"][i].type;
                                data["select"] = s["setting_list"][i].select;
                                data["description"] = s["setting_list"][i].description;
                                json_data.push(data);
                            }
                            else if (s["setting_list"][i].type == "checkbox") {
                                var data = {};
                                data["name"] = s["setting_list"][i].name;
                                if ($("#" + s["setting_list"][i].name + "_value:checked").val() == "on") {
                                    data["value"] = true;
                                } else {
                                    data["value"] = false;
                                }
                                data["type"] = s["setting_list"][i].type;
                                data["select"] = s["setting_list"][i].select;
                                data["description"] = s["setting_list"][i].description;
                                json_data.push(data);
                            } else if (s["setting_list"][i].type == "select") {
                                var data = {};
                                data["name"] = s["setting_list"][i].name;
                                data["value"] = $("#" + s["setting_list"][i].name + "_value" + " option:selected").val();
                                data["type"] = s["setting_list"][i].type;
                                data["select"] = s["setting_list"][i].select;
                                data["description"] = s["setting_list"][i].description;
                                json_data.push(data);
                            } else {
                                //console.log("type=" + s["setting_list"][i].type);
                            }
                        }
                        // Jsonデータをサーバに送信
                        json_obj["setting_list"] = json_data;
                        $ws.send("setting:" + JSON.stringify(json_obj));
                    });
                    $(this).dialog("close");
                },
                "Cancel": function () {  //Cancelボタン
                    $(this).dialog("close");
                }
            }
        });
    });
}

// 設定読み込み
function load_setting(open_id) {
    document.getElementById(open_id).onclick = async () => {
        [fileHandle] = await window.showOpenFilePicker();
        const file = await fileHandle.getFile();
        const json_data = await file.text();
        console.log(json_data);
        // Jsonデータをサーバに送信
        $ws.send("setting:" + json_data);
    };
}

// 設定保存
function save_setting(open_id, json_file) {
    document.getElementById(open_id).onclick = async () => {
        var json_data = ""
        $.ajax({
            // jsonの読み込み
            type: "GET",
            url: json_file, // ファイルパス（相対パス）
            dataType: "json", // ファイル形式
            async: false // 非同期通信フラグ
        }).then(
            function (json) {
                // 読み込み成功時の処理
                json_data = JSON.stringify(json, null, 2);
                console.log("json=" + json_data);
            },
            function () {
                // 読み込み失敗時の処理
                console.log("読み込みに失敗しました");
            }
        );
        // Jsonを保存
        const opts = {
            suggestedName: 'setting.json',
            types: [{
                description: 'Text file',
                accept: { 'text/plain': ['.json'] },
            }],
        };
        // ファイルをどこにどんな名前で保存するか訊くダイアログを表示
        const saveHandle = await window.showSaveFilePicker(opts)
        // 保存先ファイルに書き込み準備
        const writable = await saveHandle.createWritable();
        // 先程同様に書き込んで終了
        await writable.write(json_data);
        await writable.close();
    };
}

function get_dirname(path) {
    var result = path.replace(/\\/g, '/').replace(/\/[^\/]*$/, '');
    if (result.match(/^[^\/]*\.[^\/\.]*$/)) {
        result = '';
    }
    return result.replace(/\//g, "\\");
}

function dispFile() {
    var fName = $("#inDir").val();
    alert('選択したファイルの値は' + fName + 'です');
}

function openFile(file) {
    $ws.send("openfile:" + file);
}

// 起動時の処理
$(document).ready(function () {

    // サーバに接続
    server_connect("ws://localhost:44799/wsserver")
    window.onload = function (e) {
        // サーバに接続
        //server_connect("ws://localhost:44799/wsserver")
    }

    // menu
    $(function () {
        $(".menu li").hover(
            function () {
                //クラス名「open」を付与する
                $(this).children(".menuSub").addClass("open");
                //hoverが外れた場合
            }, function () {
                //クラス名「open」を取り除く
                $(this).children(".menuSub").removeClass("open");
            }
        );
    });

    // ウインドウサイズ
    var width = 800;
    var height = 600;
    $(window).resize(function () {
        $(".outarea").height($(window).height() - 180);
    });
    // ウインドウの位置
    $(function () {
        //window.resizeTo(width, height);
        //window.moveTo((window.screen.width / 2) - (width / 2), (screen.height / 2) - (height / 2));
        //window.moveTo(0,0);
        $(".outarea").height($(window).height() - 180);
    });

    $('.outarea').scroll(function () {
        var h = $('.outarea').get(0).scrollHeight - $('.outarea').innerHeight();
        //console.log("scrollEnd=" + Math.abs($('.outarea').scrollTop() - h));
        if (Math.abs($('.outarea').scrollTop() - h) < 30) {
            // 最後までスクロールしている
            // 自動スクロールON
            $auto_scroll = true;
        } else {
            // 自動スクロールOFF
            $auto_scroll = false;
        }
        //console.log("auto_scroll=" + $auto_scroll);
    });

    // 設定ダイアログ
    setting_dialog("setting", "setting_dialog", "config/setting.json");

    // 設定保存
    save_setting("save_setting", "config/setting.json");

    // 設定読み込み
    load_setting("load_setting");

    // ハンドラ登録
    $("#stop").click(function () {
        send_message("stop");
    });

    $("#exec").click(function () {
        $('#log').empty();
        send_message("exec:" + $("#inDir").val() + "," + $("#outFile").val());
    });

    $("#open_file").click(function () {
        openFile($("#outFile").val());
    });

    select_file_dialog("search_str", "dir", "dialog1", "select_dir", "inDir");

    select_file_dialog("search_str2", "file", "dialog2", "select_file", "outFile");

    autocomp_history("inDir", "history.json")
    autocomp_history("outFile", "out_history.json")

});

