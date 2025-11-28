// frontend/lib/services/journal_service.dart
import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:flutter_application_1/state/user_session.dart';

// change to your actual backend base URL if different
const String _baseUrl = 'http://127.0.0.1:8000';

class JournalService {
  final String baseUrl;
  JournalService({this.baseUrl = _baseUrl});

  /// Submits the journal + metrics to the backend analyse endpoint.
  /// Returns the created journal_id on success.
  Future<int> submitJournal({
    required String text,
    int? screenMinutes,
    int? unlockCount,
    double? sleepHours,
    int? steps,
    // string? dominantEmotion,
  }) async {
    // get user id from session (you already use UserSession in other files)
    final userId = UserSession().userId;
    if (userId == null) {
      throw Exception('No user session available');
    }

    final url = Uri.parse('$baseUrl/journal-analyse');

    final payload = {
      'user_id': userId,
      'text': text,
      'screen_minutes': screenMinutes,
      'unlock_count': unlockCount,
      'sleep_hours': sleepHours,
      'steps': steps,
      //'dominant_emotion': dominantEmotion,
    };

    final resp = await http.post(
      url,
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode(payload),
    );

    if (resp.statusCode == 200) {
      final body = jsonDecode(resp.body);
      // expect backend to return journal_id in response
      if (body != null && body['journal_id'] != null) {
        return body['journal_id'] as int;
      }
      // fallback — server confirms but didn't return id
      return -1;
    } else {
      // bubble up server message if provided
      String err = 'Failed to save journal';
      try {
        final body = jsonDecode(resp.body);
        if (body is Map && body.containsKey('detail')) err = body['detail'].toString();
        if (body is Map && body.containsKey('message')) err = body['message'].toString();
      } catch (_) {}
      throw Exception('Server error (${resp.statusCode}): $err');
    }
  }
}
