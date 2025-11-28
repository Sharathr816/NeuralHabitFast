

// frontend/lib/pages/ai_assistant.dart
import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'package:uuid/uuid.dart';
import 'package:flutter_application_1/state/user_session.dart';

class AiAssistant extends StatefulWidget {
  const AiAssistant({super.key});

  @override
  _AiAssistantState createState() => _AiAssistantState();
}

class _AiAssistantState extends State<AiAssistant> {
  final TextEditingController _ctrl = TextEditingController();
  final ScrollController _scrollCtrl = ScrollController();
  final List<_ChatMessage> _messages = [];
  bool _isSending = false;
  String _sessionId = UserSession().userId.toString();

  // dev: point to your FastAPI endpoint
  static const String _coachUrl = 'http://127.0.0.1:8000/coach/chat';
  // history endpoint (change if your backend uses different path)
  static const String _coachHistoryUrl = 'http://127.0.0.1:8000/coach/history';

  String _sanitize(String? s) {
  if (s == null) return '';
  var out = s;

  // Remove code fences and inline code
  out = out.replaceAll(RegExp(r'```[\s\S]*?```'), '');
  out = out.replaceAll('`', '');

  // Convert markdown list markers to readable bullets beginning on their own line
  out = out.replaceAllMapped(RegExp(r'\n\s*[-\*]\s+'), (m) => '\n- ');

  // Optionally convert "1. " lists to new lines (keep numbering)
  out = out.replaceAllMapped(RegExp(r'\n\s*(\d+)\.\s+'), (m) => '\n${m.group(1)}. ');

  // Convert markdown links [text](url) -> text
  out = out.replaceAllMapped(RegExp(r'\[([^\]]+)\]\([^\)]+\)'), (m) => m.group(1) ?? '');

  // Remove bold/italic markers but keep content
  out = out.replaceAllMapped(RegExp(r'(\*\*|\*|__|~~)(.*?)\1'), (m) => m.group(2) ?? '');

  // Replace table pipes with spaced separator, keep lines
  out = out.split('\n').map((ln) {
    var l = ln.trim();
    if (l.startsWith('|')) l = l.substring(1);
    if (l.endsWith('|')) l = l.substring(0, l.length - 1);
    l = l.replaceAll(RegExp(r'\s*\|\s*'), ' | ');
    return l;
  }).join('\n');

  // Collapse >2 consecutive newlines to two (paragrah gap)
  out = out.replaceAll(RegExp(r'\n{3,}'), '\n\n');

  // collapse multiple spaces but preserve newlines
  out = out.replaceAll(RegExp(r'[ \t]{2,}'), ' ');

  // trim each line
  out = out.split('\n').map((l) => l.trim()).where((l) => l.isNotEmpty).join('\n');

  return out.trim();
}



  @override
  void initState() {
    super.initState();
    _loadHistory(); // load server history when screen opens
    //_startCoachSession(); // start session if no history
  }

  
Future<void> _loadHistory() async {
  try {
    final uri = Uri.parse('http://127.0.0.1:8000/coach/history?session_id=$_sessionId');
    final resp = await http.get(uri, headers: {'Content-Type': 'application/json'});
    if (resp.statusCode != 200) return;

    final body = jsonDecode(resp.body);
    if (body is! Map || !body.containsKey('history')) return;

    final raw = body['history'] as List<dynamic>;
    final userRoles = {'user', 'human', 'me', 'self', 'sender', 'client'};

    final parsed = raw.map((e) {
      final m = (e as Map<String, dynamic>);
      final roleRaw = (m['role'] ?? m['author'] ?? '').toString().toLowerCase();
      final contentRaw = (m['text'] ?? m['message'] ?? m['content'] ?? '').toString();
      DateTime? ts;
      if (m.containsKey('ts') && m['ts'] != null) ts = DateTime.tryParse(m['ts'].toString());
      final author = userRoles.contains(roleRaw) ? Author.user : Author.bot;
      return _ChatMessage(content: _sanitize(contentRaw), author: author, ts: ts);
    }).toList();

    parsed.sort((a, b) {
      final at = a.ts ?? DateTime.fromMillisecondsSinceEpoch(0);
      final bt = b.ts ?? DateTime.fromMillisecondsSinceEpoch(0);
      return at.compareTo(bt);
    });

    setState(() {
      _messages
        ..clear()
        ..addAll(parsed);
    });

    WidgetsBinding.instance.addPostFrameCallback((_) => _scrollToBottom());
  } catch (e) { debugPrint('loadHistory err: $e'); }
}

// to get into analysis mode if no prior history
// Future<void> _startCoachSession() async {
//   // avoid spamming if somehow called this twice
//   if (_messages.isNotEmpty) return;

//   setState(() {
//     _isSending = true;
//   });

//   try {
//     final resp = await http.post(
//       Uri.parse(_coachUrl),
//       headers: {'Content-Type': 'application/json'},
//       body: jsonEncode({
//         'session_id': _sessionId,
//         'message': "", // fake input to trigger first-turn analysis
//       }),
//     );

//     if (resp.statusCode == 200) {
//       final body = jsonDecode(resp.body);

//       if (body is Map && body.containsKey('history')) {
//         final hist = (body['history'] as List<dynamic>).map((e) {
//           final m = e as Map<String, dynamic>;
//           return _ChatMessage(
//             content: _sanitize(
//               m['text']?.toString() ?? m['message']?.toString() ?? '',
//             ),
//             author: (m['role'] == 'user') ? Author.user : Author.bot,
//             ts: m.containsKey('ts')
//                 ? DateTime.tryParse(m['ts']?.toString() ?? '')
//                 : null,
//           );
//         }).toList();

//         setState(() {
//           _messages
//             ..clear()
//             ..addAll(hist);
//         });
//       } else {
//         final reply =
//             body['answer'] as String? ?? body['reply'] as String? ?? 'No reply';
//         setState(() {
//           _messages.add(
//             _ChatMessage(
//               content: _sanitize(reply),
//               author: Author.bot,
//               ts: DateTime.now(),
//             ),
//           );
//         });
//       }
//     } else {
//       setState(() {
//         _messages.add(
//           _ChatMessage(
//             content: 'Error ${resp.statusCode}: ${resp.body}',
//             author: Author.bot,
//             ts: DateTime.now(),
//           ),
//         );
//       });
//     }
//   } catch (e) {
//     setState(() {
//       _messages.add(
//         _ChatMessage(
//           content: 'Network error: $e',
//           author: Author.bot,
//           ts: DateTime.now(),
//         ),
//       );
//     });
//   } finally {
//     setState(() {
//       _isSending = false;
//     });
//     _scrollToBottom();
//   }
// }



  Future<void> _sendMessage() async {
    final text = _ctrl.text.trim();
    if (text.isEmpty) return;

    // optimistic UI: add user's message
    setState(() {
      _messages.add(
        _ChatMessage(content: text, author: Author.user, ts: DateTime.now()),
      );
      _isSending = true;
      _ctrl.clear();
    });

    _scrollToBottom();

    try {
      final resp = await http.post(
        Uri.parse(_coachUrl),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({'session_id': _sessionId, 'message': text}),
      );

      if (resp.statusCode == 200) {
        final body = jsonDecode(resp.body);
        // prefer canonical history if server returns it
        if (body is Map && body.containsKey('history')) {
          final hist = (body['history'] as List<dynamic>).map((e) {
            final m = e as Map<String, dynamic>;
            return _ChatMessage(
              content: _sanitize(
                m['text']?.toString() ?? m['message']?.toString() ?? '',
              ),
              author: (m['role'] == 'user') ? Author.user : Author.bot,
              ts: m.containsKey('ts')
                  ? DateTime.tryParse(m['ts']?.toString() ?? '')
                  : null,
            );
          }).toList();

          setState(() {
            _messages.clear();
            _messages.addAll(hist);
          });
        } else {
          // fallback to 'reply' string
          final reply = body['reply'] as String? ?? 'No reply';
          setState(() {
            _messages.add(
              _ChatMessage(
                content: _sanitize(reply),
                author: Author.bot,
                ts: DateTime.now(),
              ),
            );
          });
        }
      } else {
        setState(() {
          _messages.add(
            _ChatMessage(
              content: 'Error ${resp.statusCode}: ${resp.body}',
              author: Author.bot,
              ts: DateTime.now(),
            ),
          );
        });
      }
    } catch (e) {
      setState(() {
        _messages.add(
          _ChatMessage(
            content: 'Network error: $e',
            author: Author.bot,
            ts: DateTime.now(),
          ),
        );
      });
    } finally {
      setState(() => _isSending = false);
      _scrollToBottom();
    }
  }

void _scrollToBottom() {
  WidgetsBinding.instance.addPostFrameCallback((_) {
    if (_scrollCtrl.hasClients) {
      _scrollCtrl.animateTo(
        _scrollCtrl.position.maxScrollExtent,
        duration: const Duration(milliseconds: 200),
        curve: Curves.easeOut,
      );
    }
  });
}


  @override
  void dispose() {
    _ctrl.dispose();
    _scrollCtrl.dispose();
    super.dispose();
  }

  Widget _buildMessageTile(_ChatMessage m) {
  final isUser = m.author == Author.user;
  final bubbleColor = isUser ? Color(0xFFDCF8C6) : Colors.white;
  final textColor = Colors.black87;
  final radius = BorderRadius.only(
    topLeft: Radius.circular(16),
    topRight: Radius.circular(16),
    bottomLeft: Radius.circular(isUser ? 12 : 0),
    bottomRight: Radius.circular(isUser ? 0 : 12),
  );

  return Container(
    margin: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
    child: Row(
      mainAxisAlignment: isUser ? MainAxisAlignment.end : MainAxisAlignment.start,
      crossAxisAlignment: CrossAxisAlignment.end,
      children: [
        if (!isUser) const SizedBox(width: 6),
        Flexible(
          child: Container(
            constraints: BoxConstraints(maxWidth: MediaQuery.of(context).size.width * 0.78),
            padding: const EdgeInsets.symmetric(vertical: 10, horizontal: 12),
            decoration: BoxDecoration(
              color: bubbleColor,
              borderRadius: radius,
              boxShadow: [BoxShadow(color: Colors.black12, blurRadius: 2, offset: Offset(0,1))],
            ),
            child: Column(
              crossAxisAlignment: isUser ? CrossAxisAlignment.end : CrossAxisAlignment.start,
              children: [
                SelectableText(
                  m.content,
                  style: TextStyle(color: textColor, fontSize: 15, height: 1.35),
                  showCursor: false,
                  // SelectableText wraps by default. If you prefer non-selectable:
                  // Text(m.content, style: ..., softWrap: true, overflow: TextOverflow.visible)
                ),

                const SizedBox(height: 6),
                Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Text(
                      m.ts != null ? _formatTime(m.ts) : '',
                      style: TextStyle(fontSize: 10, color: Colors.black45),
                    ),
                    if (isUser) const SizedBox(width: 6),
                    if (isUser) Icon(Icons.done_all, size: 14, color: Colors.blueAccent),
                  ],
                )
              ],
            ),
          ),
        ),
        if (isUser) const SizedBox(width: 6),
      ],
    ),
  );
}


  String _formatTime(DateTime? t) {
    if (t == null) return '';
    final dt = t.toLocal();
    final hh = dt.hour.toString().padLeft(2, '0');
    final mm = dt.minute.toString().padLeft(2, '0');
    return '$hh:$mm';
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Scaffold(
      appBar: AppBar(
        title: const Text('AI Assistant'),
        actions: [
          IconButton(
              tooltip: 'Clear chat history',
              icon: const Icon(Icons.refresh),
              onPressed: () async {
                try {
                  // POST JSON body (safer than query params)
                  final uri = Uri.parse('http://127.0.0.1:8000/coach/clear_history');
                  final resp = await http.post(
                    uri,
                    headers: {'Content-Type': 'application/json'},
                    body: jsonEncode({'session_id': _sessionId}),
                  );

                  if (resp.statusCode == 200) {
                    // server confirmed clear -> clear UI and re-load canonical history (should be empty)
                    setState(() => _messages.clear());

                    // optional: reload from server to be 100% synced
                    await _loadHistory();
                  } else {
                    // show simple error bubble in UI
                    setState(() => _messages.add(
                      _ChatMessage(content: 'Error clearing history: ${resp.statusCode}', author: Author.bot),
                    ));
                  }
                } catch (e) {
                  setState(() => _messages.add(
                    _ChatMessage(content: 'Network error clearing history: $e', author: Author.bot),
                  ));
                }
              },
            ),

        ],
      ),
      body: Column(
        children: [
          Expanded(
            child: ListView.builder(
              controller: _scrollCtrl,
              padding: const EdgeInsets.symmetric(vertical: 12),
              itemCount: _messages.length,
              itemBuilder: (_, i) => _buildMessageTile(_messages[i]),
            ),
          ),
          if (_isSending)
            LinearProgressIndicator(
              minHeight: 3,
              color: theme.colorScheme.primary,
            ),
          SafeArea(
            child: Padding(
              padding: const EdgeInsets.symmetric(
                horizontal: 12.0,
                vertical: 8,
              ),
              child: Row(
                children: [
                  Expanded(
                    child: TextField(
                      controller: _ctrl,
                      textInputAction: TextInputAction.send,
                      onSubmitted: (_) => _sendMessage(),
                      decoration: const InputDecoration(
                        hintText: 'Ask the coach…',
                        border: OutlineInputBorder(),
                      ),
                    ),
                  ),
                  const SizedBox(width: 8),
                  ElevatedButton(
                    onPressed: _isSending ? null : _sendMessage,
                    child: const Icon(Icons.send),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}

enum Author { user, bot }

class _ChatMessage {
  final String content;
  final Author author;
  final DateTime? ts;

  _ChatMessage({required this.content, required this.author, this.ts});

  factory _ChatMessage.fromJson(Map<String, dynamic> j) {
    final role = (j['role'] ?? j['author'] ?? '').toString().toLowerCase();
    final content = (j['text'] ?? j['message'] ?? j['content'] ?? '')
        .toString();
    DateTime? ts;
    if (j.containsKey('ts')) {
      try {
        ts = DateTime.parse(j['ts'].toString());
      } catch (_) {
        ts = null;
      }
    }
    return _ChatMessage(
      content: content,
      author: role == 'user' ? Author.user : Author.bot,
      ts: ts,
    );
  }

  Map<String, dynamic> toJson() => {
    'role': author == Author.user ? 'user' : 'assistant',
    'text': content,
    'ts': ts?.toIso8601String(),
  };
}
