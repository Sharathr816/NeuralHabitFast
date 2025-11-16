import 'dart:convert';

class UserProfile {
  final int userId;
  final String name;
  final String email;
  final DateTime signupDate;

  UserProfile({
    required this.userId,
    required this.name,
    required this.email,
    required this.signupDate,
  });

  Map<String, dynamic> toMap() {
    return {
      'userId': userId,
      'name': name,
      'email': email,
      'signupDate': signupDate.toIso8601String(),
    };
  }

  factory UserProfile.fromMap(Map<String, dynamic> map) {
    return UserProfile(
      userId: map['userId'] as int,
      name: map['name'] as String,
      email: map['email'] as String,
      signupDate: DateTime.parse(map['signupDate'] as String),
    );
  }

  String toJson() => jsonEncode(toMap());

  factory UserProfile.fromJson(String source) =>
      UserProfile.fromMap(jsonDecode(source) as Map<String, dynamic>);
}