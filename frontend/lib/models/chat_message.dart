// frontend/lib/models/chat_message.dart
class ChatMessage {
  final String role; // 'user' | 'assistant' | 'system'
  final String text;
  final DateTime ts;

  ChatMessage({required this.role, required this.text, required this.ts});

  factory ChatMessage.fromJson(Map<String, dynamic> j) {
    return ChatMessage(
      role: j['role'] ?? 'assistant',
      text: j['text'] ?? '',
      ts: j.containsKey('ts') ? DateTime.parse(j['ts']) : DateTime.now(),
    );
  }

  Map<String, dynamic> toJson() => {
        'role': role,
        'text': text,
        'ts': ts.toIso8601String(),
      };
}
