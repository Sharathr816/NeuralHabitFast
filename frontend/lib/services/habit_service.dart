import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:flutter_application_1/config.dart';
import 'package:flutter_application_1/state/user_session.dart';

class HabitService {
  final UserSession _session = UserSession();

  int? get _userId => _session.user?.userId;

  Future<List<dynamic>> fetchHabits() async {
    final uid = _userId;
    if (uid == null) return [];
    final res = await http.get(Uri.parse('$backendBaseUrl/user/$uid/habits'));
    if (res.statusCode >= 400) throw Exception('Failed to load habits');
    final data = jsonDecode(res.body);
    if (data is Map && data.containsKey('habits')) return data['habits'];
    if (data is List) return data;
    return [];
  }

  Future<Map<String, dynamic>> createHabit({
    required String title,
    required String category,
    required int days,
    required bool isPositive,
  }) async {
    final uid = _userId;
    if (uid == null) throw Exception('Not authenticated');
    final payload = {
      'user_id': uid,
      'habit_name': title,
      'category': category,
      'number_of_days': days,
      'habit_type': isPositive ? 'positive' : 'negative',
    };
    final res = await http.post(
      Uri.parse('$backendBaseUrl/user/habits'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode(payload),
    );
    if (res.statusCode >= 400) throw Exception('Failed to create habit');
    return jsonDecode(res.body) as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> checkHabit(int habitId) async {
    final res = await http.post(
      Uri.parse('$backendBaseUrl/user/habits/$habitId/check'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({'checked': true}),
    );
    if (res.statusCode >= 400) throw Exception('Failed to check habit');
    return jsonDecode(res.body) as Map<String, dynamic>;
  }

  Future<List<dynamic>> fetchTasks() async {
    final uid = _userId;
    if (uid == null) return [];
    final res = await http.get(Uri.parse('$backendBaseUrl/user/$uid/tasks'));
    if (res.statusCode >= 400) throw Exception('Failed to load tasks');
    final data = jsonDecode(res.body);
    if (data is Map && data.containsKey('tasks')) return data['tasks'];
    if (data is List) return data;
    return [];
  }

  Future<Map<String, dynamic>> createTask({
    required String title,
    DateTime? deadline,
  }) async {
    final uid = _userId;
    if (uid == null) throw Exception('Not authenticated');
    final payload = {
      'user_id': uid,
      'title': title,
      'deadline': deadline?.toIso8601String(),
    };
    final res = await http.post(
      Uri.parse('$backendBaseUrl/user/tasks'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode(payload),
    );
    if (res.statusCode >= 400) throw Exception('Failed to create task');
    final data = jsonDecode(res.body) as Map<String, dynamic>;
    // backend returns {status:ok, task_id: id}
    return data;
  }

  Future<Map<String, dynamic>> completeTask(int taskId) async {
    final res = await http.post(
      Uri.parse('$backendBaseUrl/user/tasks/$taskId/complete'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({}),
    );
    if (res.statusCode >= 400) throw Exception('Failed to complete task');
    return jsonDecode(res.body) as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> deleteTask(int taskId) async {
    final res = await http.delete(
      Uri.parse('$backendBaseUrl/user/tasks/$taskId'),
      headers: {'Content-Type': 'application/json'},
    );
    if (res.statusCode >= 400) throw Exception('Failed to delete task');
    return jsonDecode(res.body) as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> deleteHabit(int habitId) async {
    final res = await http.delete(
      Uri.parse('$backendBaseUrl/user/habits/$habitId'),
      headers: {'Content-Type': 'application/json'},
    );
    if (res.statusCode >= 400) throw Exception('Failed to delete habit');
    return jsonDecode(res.body) as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> fetchStats() async {
    final uid = _userId;
    if (uid == null) throw Exception('Not authenticated');
    final res = await http.get(Uri.parse('$backendBaseUrl/user/$uid/stats'));
    if (res.statusCode >= 400) throw Exception('Failed to fetch stats');
    return jsonDecode(res.body) as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> playHealthPotion({bool won = false}) async {
    final uid = _userId;
    if (uid == null) throw Exception('Not authenticated');
    final res = await http.post(
      Uri.parse('$backendBaseUrl/user/$uid/minigame/play_health_potion'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({'won': won}),
    );
    if (res.statusCode >= 400) throw Exception('Failed to play minigame');
    return jsonDecode(res.body) as Map<String, dynamic>;
  }
}

final habitService = HabitService();
