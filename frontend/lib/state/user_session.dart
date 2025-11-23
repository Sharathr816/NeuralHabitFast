import 'package:flutter/foundation.dart';
import 'package:flutter_application_1/models/user_profile.dart';

class UserSession extends ChangeNotifier {
  static final UserSession _instance = UserSession._internal();
  factory UserSession() => _instance;
  UserSession._internal();

  UserProfile? _user;
  String? _token; // placeholder for future backend token

  UserProfile? get user => _user;
  String? get token => _token;
  bool get isAuthenticated => _user != null;
  String? get userId => _user?.userId.toString(); // adapt if id type is String/int

  void setUser(UserProfile? user, {String? token}) {
    _user = user;
    _token = token;
    notifyListeners();
  }

  void clear() {
    _user = null;
    _token = null;
    notifyListeners();
  }
}