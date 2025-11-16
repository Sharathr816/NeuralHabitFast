import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:flutter_application_1/config.dart';
import 'package:flutter_application_1/state/user_session.dart';

class JournalService {
  final UserSession _session = UserSession();

  Future<String> submitJournal({
    required String text,
    int? screenMinutes,
    int? unlockCount,
    double? sleepHours,
    int? steps,
    String? dominantEmotion,
    double? dominantEmotionScore,
  }) async {
    final user = _session.user;
    if (user == null) {
      throw Exception('You must be logged in to submit a journal.');
    }

    final payload = {
      'user_id': user.userId,
      'text': text,
      if (screenMinutes != null) 'screen_minutes': screenMinutes,
      if (unlockCount != null) 'unlock_count': unlockCount,
      if (sleepHours != null) 'sleep_hours': sleepHours,
      if (steps != null) 'steps': steps,
      if (dominantEmotion != null) 'dominant_emotion': dominantEmotion,
      if (dominantEmotionScore != null) 'dominant_emotion_score': dominantEmotionScore,
    };

    final response = await http.post(
      Uri.parse('$backendBaseUrl/ingest/journal'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode(payload),
    );

    if (response.statusCode >= 400) {
      final detail = _extractError(response.body);
      throw Exception('Failed to submit journal: $detail');
    }

    final data = jsonDecode(response.body) as Map<String, dynamic>;
    return data['journal_id'].toString();
  }

  String _extractError(String body) {
    try {
      final data = jsonDecode(body) as Map<String, dynamic>;
      return data['detail']?.toString() ?? 'Unknown error';
    } catch (_) {
      return 'Unknown error';
    }
  }
}

