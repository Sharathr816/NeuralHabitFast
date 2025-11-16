import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:flutter_application_1/config.dart';
import 'package:flutter_application_1/state/user_session.dart';

class CoachService {
  final UserSession _session = UserSession();

  Future<Map<String, dynamic>> getCoaching() async {
    final user = _session.user;
    if (user == null) {
      throw Exception('You must be logged in to get coaching.');
    }

    final response = await http.post(
      Uri.parse('$backendBaseUrl/coach/get-coaching?user_id=${user.userId}'),
      headers: {'Content-Type': 'application/json'},
    );

    if (response.statusCode >= 400) {
      final detail = _extractError(response.body);
      throw Exception('Failed to get coaching: $detail');
    }

    return jsonDecode(response.body) as Map<String, dynamic>;
  }

  Future<List<Map<String, dynamic>>> getCoachSessions({int limit = 10}) async {
    final user = _session.user;
    if (user == null) {
      throw Exception('You must be logged in to view coach sessions.');
    }

    final response = await http.get(
      Uri.parse('$backendBaseUrl/coach/sessions/${user.userId}?limit=$limit'),
      headers: {'Content-Type': 'application/json'},
    );

    if (response.statusCode >= 400) {
      final detail = _extractError(response.body);
      throw Exception('Failed to get coach sessions: $detail');
    }

    final data = jsonDecode(response.body);
    if (data is List) {
      return data.cast<Map<String, dynamic>>();
    }
    return [];
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


