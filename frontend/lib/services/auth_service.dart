import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';
import 'package:flutter_application_1/config.dart';
import 'package:flutter_application_1/models/user_profile.dart';
import 'package:flutter_application_1/state/user_session.dart';

class AuthService {
  static const _userKey = 'neuralhabit.user';

  final UserSession _session = UserSession();

  Future<void> hydrate() async {
    final prefs = await SharedPreferences.getInstance();
    final raw = prefs.getString(_userKey);
    if (raw == null) return;
    try {
      final user = UserProfile.fromJson(raw);
      _session.setUser(user);
    } catch (_) {
      await prefs.remove(_userKey);
    }
  }

  Future<UserProfile> signup({
    required String name,
    required String email,
    required String password,
  }) async {
    final payload = {
      'name': name,
      'email': email,
      'password': password,
    };

    final response = await http.post(
      Uri.parse('$backendBaseUrl/auth/signup'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode(payload),
    );

    if (response.statusCode >= 400) {
      throw Exception(_extractError(response.body, fallback: 'Failed to sign up'));
    }

    final user = _userFromResponse(response.body);
    await _persistUser(user);
    _session.setUser(user);
    return user;
  }

  Future<UserProfile> login({
    required String email,
    required String password,
  }) async {
    final response = await http.post(
      Uri.parse('$backendBaseUrl/auth/login'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({'email': email, 'password': password}),
    );

    if (response.statusCode >= 400) {
      throw Exception(_extractError(response.body, fallback: 'Invalid credentials'));
    }

    final user = _userFromResponse(response.body);
    await _persistUser(user);
    _session.setUser(user);
    return user;
  }

  Future<void> logout() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(_userKey);
    _session.clear();
  }

  UserProfile _userFromResponse(String body) {
    final data = jsonDecode(body) as Map<String, dynamic>;
    return UserProfile(
      userId: data['user_id'] as int,
      name: data['name'] as String,
      email: data['email'] as String,
      signupDate: DateTime.parse(data['signup_date'] as String),
    );
  }

  Future<void> _persistUser(UserProfile user) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_userKey, user.toJson());
  }

  String _extractError(String body, {required String fallback}) {
    try {
      final data = jsonDecode(body) as Map<String, dynamic>;
      return data['detail']?.toString() ?? fallback;
    } catch (_) {
      return fallback;
    }
  }
}