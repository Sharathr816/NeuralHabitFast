import 'dart:math';

import 'package:flutter/foundation.dart';

class GamificationChange {
  final int xpDelta;
  final int hpDelta;
  final int levelDelta;

  const GamificationChange({
    this.xpDelta = 0,
    this.hpDelta = 0,
    this.levelDelta = 0,
  });

  bool get hasChange => xpDelta != 0 || hpDelta != 0 || levelDelta != 0;
}

class GamificationStats extends ChangeNotifier {
  GamificationStats();

  // Base stats (can be replaced with persisted data later)
  int _currentXP = 850;
  int _currentLevel = 5;
  int _currentHP = 85; // Health points out of 100
  int _currentStreak = 0;
  int _totalHabitsCompleted = 42;
  int _positiveHabitsCompleted = 38;
  int _negativeHabitsLogged = 4;
  
  // Track last login date for streak calculation
  String? _lastLoginDate;

  static const int _xpPerPositiveHabit = 25;
  static const int _hpPenaltyPerNegativeHabit = 10;
  static const int _dailyHealthBonus = 20;
  static const int _maxDailyGamePlays = 3;

  // Track dates that have received daily bonus (normalized to year-month-day)
  final Set<String> _dailyBonusDates = {};
  
  // Track daily game plays: date string -> play count
  final Map<String, int> _dailyGamePlays = {};

  int get currentXP => _currentXP;
  int get currentLevel => _currentLevel;
  int get currentHP => _currentHP;
  int get currentStreak => _currentStreak;
  int get totalHabitsCompleted => _totalHabitsCompleted;
  int get positiveHabitsCompleted => _positiveHabitsCompleted;
  int get negativeHabitsLogged => _negativeHabitsLogged;

  int get xpForCurrentLevel => (_currentLevel - 1) * 200;
  int get xpForNextLevel => _currentLevel * 200;
  int get xpProgress => _currentXP - xpForCurrentLevel;
  int get xpNeeded => xpForNextLevel - xpForCurrentLevel;
  double get xpProgressPercentage => xpNeeded == 0 ? 0 : xpProgress / xpNeeded;

  void _normalizeLevel() {
    final int previousLevel = _currentLevel;
    
    while (_currentXP >= xpForNextLevel) {
      _currentLevel += 1;
    }

    while (_currentLevel > 1 && _currentXP < xpForCurrentLevel) {
      _currentLevel -= 1;
    }
    
    // If level increased, restore HP to 100
    if (_currentLevel > previousLevel) {
      _currentHP = 100;
    }
  }

  void _changeLevel(int delta) {
    if (delta == 0) return;
    final previousLevel = _currentLevel;
    _currentLevel = max(1, _currentLevel + delta);

    if (_currentLevel < previousLevel) {
      final int newLevelNextXP = xpForNextLevel;
      if (_currentXP >= newLevelNextXP) {
        _currentXP = newLevelNextXP - 1;
      }
    }

    _normalizeLevel();
  }

  void _modifyXP(int delta) {
    if (delta == 0) return;
    _currentXP = max(0, _currentXP + delta);
    _normalizeLevel();
  }

  void _modifyHP(int delta) {
    if (delta == 0) return;
    _currentHP = (_currentHP + delta).clamp(0, 100);
  }

  GamificationChange registerPositiveHabitChange({
    required bool wasCompleted,
    required bool isCompleted,
  }) {
    if (wasCompleted == isCompleted) return const GamificationChange();

    final int previousXP = _currentXP;
    final int previousLevel = _currentLevel;

    int delta = 0;
    if (isCompleted) {
      delta = _xpPerPositiveHabit;
      _totalHabitsCompleted += 1;
      _positiveHabitsCompleted += 1;
    } else {
      delta = -_xpPerPositiveHabit;
      _totalHabitsCompleted = max(0, _totalHabitsCompleted - 1);
      _positiveHabitsCompleted = max(0, _positiveHabitsCompleted - 1);
    }

    _modifyXP(delta);

    final int xpDelta = _currentXP - previousXP;
    final int levelDelta = _currentLevel - previousLevel;

    notifyListeners();
    return GamificationChange(xpDelta: xpDelta, levelDelta: levelDelta);
  }

  GamificationChange registerNegativeHabitChange({
    required bool wasCompleted,
    required bool isCompleted,
  }) {
    if (wasCompleted == isCompleted) return const GamificationChange();

    final int previousHP = _currentHP;
    final int previousLevel = _currentLevel;
    final int previousXP = _currentXP;

    int hpDelta = 0;

    if (isCompleted) {
      hpDelta = -_hpPenaltyPerNegativeHabit;
      _negativeHabitsLogged += 1;
    } else {
      hpDelta = _hpPenaltyPerNegativeHabit;
      _negativeHabitsLogged = max(0, _negativeHabitsLogged - 1);
    }

    _modifyHP(hpDelta);

    final int actualHPDelta = _currentHP - previousHP;

    if (isCompleted) {
      final bool reachedZero = previousHP > 0 && _currentHP == 0;
      final bool alreadyZero = previousHP == 0;
      if ((reachedZero || alreadyZero) && _currentLevel > 1) {
        _changeLevel(-1);
      }
    }

    final int levelDelta = _currentLevel - previousLevel;
    final int xpDelta = _currentXP - previousXP;

    notifyListeners();
    return GamificationChange(
      hpDelta: actualHPDelta,
      levelDelta: levelDelta,
      xpDelta: xpDelta,
    );
  }

  GamificationChange awardHealth(int amount) {
    if (amount <= 0) return const GamificationChange();

    final int previousHP = _currentHP;
    _modifyHP(amount);
    final int hpDelta = _currentHP - previousHP;

    if (hpDelta != 0) {
      notifyListeners();
    }

    return GamificationChange(hpDelta: hpDelta);
  }

  // Normalize date to string for comparison (YYYY-MM-DD)
  String _normalizeDateString(DateTime date) {
    return '${date.year}-${date.month.toString().padLeft(2, '0')}-${date.day.toString().padLeft(2, '0')}';
  }

  // Check and award daily health bonus (only once per day)
  GamificationChange? checkAndAwardDailyBonus() {
    final DateTime now = DateTime.now();
    final String todayKey = _normalizeDateString(now);

    // Check if today has already received the bonus
    if (_dailyBonusDates.contains(todayKey)) {
      return null; // Already received today
    }

    // Award the bonus and mark today as received
    _dailyBonusDates.add(todayKey);
    final change = awardHealth(_dailyHealthBonus);

    return change;
  }

  // Update login streak based on consecutive daily logins
  void updateLoginStreak() {
    final DateTime now = DateTime.now();
    final String todayKey = _normalizeDateString(now);

    // If no previous login recorded, start streak at 1
    if (_lastLoginDate == null) {
      _lastLoginDate = todayKey;
      _currentStreak = 1;
      notifyListeners();
      return;
    }

    // If already logged in today, don't change streak
    if (_lastLoginDate == todayKey) {
      return;
    }

    // Calculate days difference
    final DateTime lastLogin = _parseDateString(_lastLoginDate!);
    final DateTime today = _parseDateString(todayKey);
    final int daysDifference = today.difference(lastLogin).inDays;

    if (daysDifference == 1) {
      // Consecutive day: increment streak
      _currentStreak += 1;
    } else if (daysDifference > 1) {
      // Gap in login: reset streak to 1 (today is day 1 of new streak)
      _currentStreak = 1;
    }
    // If daysDifference is 0, it's the same day (already handled above)

    // Update last login date
    _lastLoginDate = todayKey;
    notifyListeners();
  }

  // Parse date string back to DateTime (YYYY-MM-DD format)
  DateTime _parseDateString(String dateString) {
    final parts = dateString.split('-');
    return DateTime(int.parse(parts[0]), int.parse(parts[1]), int.parse(parts[2]));
  }

  // Get the date string for today (for external checks)
  String getTodayKey() {
    return _normalizeDateString(DateTime.now());
  }

  // Check if today has already received the bonus (for UI display)
  bool hasReceivedDailyBonusToday() {
    return _dailyBonusDates.contains(getTodayKey());
  }

  // Check if mini-game can be played today (max 3 times per day)
  bool canPlayMiniGameToday() {
    final String todayKey = getTodayKey();
    final int playsToday = _dailyGamePlays[todayKey] ?? 0;
    return playsToday < _maxDailyGamePlays;
  }

  // Get remaining plays for today
  int getRemainingGamePlaysToday() {
    final String todayKey = getTodayKey();
    final int playsToday = _dailyGamePlays[todayKey] ?? 0;
    return _maxDailyGamePlays - playsToday;
  }

  // Record a mini-game play (call this when game is completed)
  void recordMiniGamePlay() {
    final String todayKey = getTodayKey();
    final int currentPlays = _dailyGamePlays[todayKey] ?? 0;
    _dailyGamePlays[todayKey] = currentPlays + 1;
    notifyListeners();
  }

  // Award XP for completing a task before deadline
  GamificationChange awardTaskCompletionXP() {
    const int taskXP = 20;
    final int previousXP = _currentXP;
    final int previousLevel = _currentLevel;

    _modifyXP(taskXP);

    final int xpDelta = _currentXP - previousXP;
    final int levelDelta = _currentLevel - previousLevel;

    notifyListeners();
    return GamificationChange(xpDelta: xpDelta, levelDelta: levelDelta);
  }

  // Penalize HP for missing task deadline
  GamificationChange penalizeMissedTask() {
    const int taskHPPenalty = 10;
    final int previousHP = _currentHP;

    _modifyHP(-taskHPPenalty);

    final int hpDelta = _currentHP - previousHP;

    notifyListeners();
    return GamificationChange(hpDelta: hpDelta);
  }
}

final gamificationStats = GamificationStats();
