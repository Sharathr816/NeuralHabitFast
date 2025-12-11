import 'package:flutter/material.dart';
import 'package:flutter_application_1/models/gamification_stats.dart';
import 'package:flutter_application_1/pages/gamificationpage.dart';
import 'package:flutter_application_1/pages/journal.dart';
import 'package:flutter_application_1/pages/ai_assistant.dart';
import 'package:flutter_application_1/services/auth_service.dart';
import 'package:flutter_application_1/services/habit_service.dart';
import 'package:flutter_application_1/state/user_session.dart';
import 'package:table_calendar/table_calendar.dart';

class FirstPage extends StatefulWidget {
  const FirstPage({super.key});

  @override
  State<FirstPage> createState() => _FirstPageState();
}

class _FirstPageState extends State<FirstPage> {
  final _controller = TextEditingController();
  final UserSession _session = UserSession();
  int _selectedIndex = 0;
  final TextEditingController _habitTitleController = TextEditingController();
  bool _isDeleteMode = false;
  final Set<int> _selectedHabitsForDeletion = {};
  String _selectedFilter = "All"; // Track selected category filter

  // Calendar & tasks state
  DateTime _focusedDay = DateTime.now();
  DateTime _selectedDay = DateTime.now();
  final Map<DateTime, List<_CalendarTask>> _tasksByDate = {};
  final Map<DateTime, _DailyProgressEntry> _dailyProgressByDate = {};
  // Track tasks that have already been penalized for missed deadlines
  final Set<String> _penalizedTasks = {};

  // Habits will be loaded from the backend for the current user
  final List<_Habit> _habits = [];

  final AuthService _authService = AuthService();
  final habitService = HabitService();

  @override
  void initState() {
    super.initState();
    // Check and award daily health bonus when app opens
    // Also update login streak
    WidgetsBinding.instance.addPostFrameCallback((_) {
      gamificationStats.updateLoginStreak();
      _checkDailyBonus();
      _checkMissedTaskDeadlines();
      _loadInitialData();
    });
  }

  Future<void> _loadInitialData() async {
    try {
      // Load habits
      final rawHabits = await habitService.fetchHabits();
      final List<_Habit> loaded = [];
      for (final h in rawHabits) {
        try {
          final map = h as Map<String, dynamic>;
          loaded.add(
            _Habit(
              id: map['id'] is int
                  ? map['id'] as int
                  : (map['habit_id'] is int ? map['habit_id'] as int : null),
              title:
                  map['habit_name']?.toString() ??
                  map['title']?.toString() ??
                  'Habit',
              category: map['category']?.toString() ?? 'Other',
              days: (map['number_of_days'] is num)
                  ? (map['number_of_days'] as num).toInt()
                  : 0,
              completed: map['is_checked'] == true || map['checked'] == true,
              isPositive:
                  (map['habit_type']?.toString() ?? 'positive') == 'positive',
            ),
          );
        } catch (_) {}
      }

      // Load stats and sync
      try {
        final stats = await habitService.fetchStats();
        gamificationStats.updateFromServer(stats);
      } catch (_) {}

      // Load tasks from backend and map into calendar by normalized date
      try {
        final rawTasks = await habitService.fetchTasks();
        final Map<DateTime, List<_CalendarTask>> loadedTasks = {};
        for (final t in rawTasks) {
          try {
            final map = t as Map<String, dynamic>;
            final String? dl = map['deadline']?.toString();
            DateTime? deadline;
            if (dl != null && dl.isNotEmpty) {
              try {
                deadline = DateTime.parse(dl).toLocal();
              } catch (_) {
                deadline = null;
              }
            }
            final DateTime key = deadline != null
                ? _normalizeDate(deadline)
                : _normalizeDate(DateTime.now());
            final task = _CalendarTask(
              id: map['id'] is int
                  ? map['id'] as int
                  : (map['task_id'] is int ? map['task_id'] as int : null),
              title: map['title']?.toString() ?? 'Task',
              deadline: deadline,
              completed: map['completed'] == true,
            );
            loadedTasks.putIfAbsent(key, () => []).add(task);
          } catch (_) {}
        }

        setState(() {
          _tasksByDate.clear();
          _tasksByDate.addAll(loadedTasks);
        });
      } catch (_) {
        // ignore task load errors
      }

      setState(() {
        _habits.clear();
        _habits.addAll(loaded);
      });
    } catch (_) {
      // ignore load errors for now
    }
  }

  void _checkMissedTaskDeadlines() {
    final DateTime now = DateTime.now();
    final List<String> missedTasks = [];

    // Check all tasks across all dates
    _tasksByDate.forEach((date, tasks) {
      for (final task in tasks) {
        if (!task.completed &&
            task.deadline != null &&
            now.isAfter(task.deadline!)) {
          // Create unique key for this task (date + title + deadline)
          final String taskKey =
              '${_normalizeDate(date).toString()}_${task.title}_${task.deadline!.toString()}';

          // Check if this task has already been penalized
          if (!_penalizedTasks.contains(taskKey)) {
            missedTasks.add(task.title);

            // Apply HP penalty
            gamificationStats.penalizeMissedTask();

            // Mark this task as penalized to prevent repeated penalties
            _penalizedTasks.add(taskKey);
          }
        }
      }
    });

    if (missedTasks.isNotEmpty && mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            'Missed deadline for ${missedTasks.length} task(s): -10 HP penalty',
            style: const TextStyle(fontWeight: FontWeight.bold),
          ),
          duration: const Duration(seconds: 3),
          backgroundColor: Colors.red,
        ),
      );
    }
  }

  void _checkDailyBonus() {
    final change = gamificationStats.checkAndAwardDailyBonus();
    if (change != null && change.hpDelta > 0 && mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            'Daily Health Bonus! +${change.hpDelta} HP 🎉',
            style: const TextStyle(fontWeight: FontWeight.bold),
          ),
          duration: const Duration(seconds: 3),
          backgroundColor: Colors.green,
        ),
      );
    }
  }

  // Get filtered habits with their original indices
  List<MapEntry<int, _Habit>> get _filteredHabitsWithIndices {
    if (_selectedFilter == "All") {
      return _habits.asMap().entries.toList();
    }
    return _habits
        .asMap()
        .entries
        .where((entry) => entry.value.category == _selectedFilter)
        .toList();
  }

  // Get filtered habits list (for completion percentage calculation)
  List<_Habit> get _filteredHabits {
    return _filteredHabitsWithIndices.map((entry) => entry.value).toList();
  }

  DateTime _normalizeDate(DateTime date) =>
      DateTime(date.year, date.month, date.day);

  List<_CalendarTask> _getTasksForDay(DateTime day) {
    return _tasksByDate[_normalizeDate(day)] ?? [];
  }

  _DailyProgressEntry? _getProgressForDay(DateTime day) {
    return _dailyProgressByDate[_normalizeDate(day)];
  }

  void _setTasksForDay(DateTime day, List<_CalendarTask> tasks) {
    final normalized = _normalizeDate(day);
    if (tasks.isEmpty) {
      _tasksByDate.remove(normalized);
    } else {
      _tasksByDate[normalized] = tasks;
    }
  }

  void _setProgressForDay(DateTime day, _DailyProgressEntry? entry) {
    final normalized = _normalizeDate(day);
    if (entry == null) {
      _dailyProgressByDate.remove(normalized);
    } else {
      _dailyProgressByDate[normalized] = entry;
    }
  }

  List<dynamic> _getCalendarEventsForDay(DateTime day) {
    final normalized = _normalizeDate(day);
    final tasks = _getTasksForDay(normalized);
    final progress = _getProgressForDay(normalized);

    final List<dynamic> events = [];
    if (tasks.isNotEmpty) {
      events.add('tasks');
    }
    if (progress != null) {
      events.add('progress');
    }
    return events;
  }

  String _formatDate(DateTime date) {
    const months = [
      'Jan',
      'Feb',
      'Mar',
      'Apr',
      'May',
      'Jun',
      'Jul',
      'Aug',
      'Sep',
      'Oct',
      'Nov',
      'Dec',
    ];
    return '${months[date.month - 1]} ${date.day}, ${date.year}';
  }

  String? _formatTime(DateTime? dateTime) {
    if (dateTime == null) return null;
    final hour = dateTime.hour % 12 == 0 ? 12 : dateTime.hour % 12;
    final minute = dateTime.minute.toString().padLeft(2, '0');
    final period = dateTime.hour >= 12 ? 'PM' : 'AM';
    return '$hour:$minute $period';
  }

  // Changed _pages from fixed list to getter for rebuilding on setState
  List<Widget> get _pages => [
    _buildMainDashboard(),
    AiAssistant(),
    JournalPage(controller: _controller, onCancel: () {}),
    GamificationPage(),
  ];

  void _navigateBottomBar(int index) {
    setState(() {
      _selectedIndex = index;
    });
  }

  String _currentUserName() {
    final user = _session.user;
    if (user == null) return 'there';
    final parts = user.name.trim().split(' ');
    return parts.isNotEmpty ? parts.first : user.name;
  }

  String _currentUserFullName() {
    return _session.user?.name ?? 'Guest User';
  }

  String _currentUserEmail() {
    return _session.user?.email ?? 'guest@neuralhabit.app';
  }

  String _currentUserSubtitle() {
    final user = _session.user;
    if (user == null) {
      return "let's build great habits!";
    }
    return "great to see you back ✨";
  }

  Future<void> _handleLogout() async {
    Navigator.pop(context);
    await _authService.logout();
    if (!mounted) return;
    Navigator.of(context).pushNamedAndRemoveUntil('/auth', (route) => false);
  }

  Widget _hoverableCard(Widget child) {
    return MouseRegion(
      cursor: SystemMouseCursors.click,
      child: InkWell(
        onTap: () {},
        hoverColor: Colors.grey[200],
        borderRadius: BorderRadius.circular(12),
        child: Container(
          margin: const EdgeInsets.only(right: 12),
          child: child,
        ),
      ),
    );
  }

  Widget _buildMainDashboard() {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Greeting & Progress
          Text.rich(
            TextSpan(
              text: 'Hi ${_currentUserName()}, ',
              style: const TextStyle(fontSize: 24, color: Colors.black),
              children: [
                TextSpan(
                  text: _currentUserSubtitle(),
                  style: TextStyle(color: Colors.teal.shade700),
                ),
              ],
            ),
          ),
          const SizedBox(height: 4),
          const Text(
            'Keep going strong with your habits!',
            style: TextStyle(color: Colors.grey),
          ),
          const SizedBox(height: 24),

          // Horizontally scrollable cards (fix overflow)
          SingleChildScrollView(
            scrollDirection: Axis.horizontal,
            child: Row(
              children: [
                _hoverableCard(
                  _buildCard(
                    title: "AI Insights",
                    content:
                        "Your morning meditation habit is showing great consistency. Consider adding an evening session for better sleep quality.",
                    footer: "See more insights",
                    icon: Icons.insights,
                  ),
                ),
                _hoverableCard(
                  _buildCard(
                    title: "Streak & XP",
                    content: "Current Streak\n0 days\n\nTotal XP\n750 XP",
                    footer: "200 XP until next level",
                    icon: Icons.local_fire_department,
                  ),
                ),
                _hoverableCard(_buildWeeklyProgress()),
              ],
            ),
          ),

          const SizedBox(height: 32),
          _buildHabitsSection(),
          _buildCalendarSection(),
        ],
      ),
    );
  }

  Widget _buildCard({
    required String title,
    required String content,
    required String footer,
    required IconData icon,
  }) {
    return Container(
      width: 280, // fixed width for consistent horizontal scroll
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.grey[100],
        borderRadius: BorderRadius.circular(12),
        boxShadow: const [
          BoxShadow(color: Colors.black12, blurRadius: 4, offset: Offset(0, 2)),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(icon, color: Colors.teal, size: 24),
          const SizedBox(height: 12),
          Text(
            title,
            style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
          ),
          const SizedBox(height: 8),
          Text(
            content,
            style: const TextStyle(fontSize: 14, color: Colors.black87),
          ),
          const SizedBox(height: 12),
          Text(
            footer,
            style: const TextStyle(fontSize: 12, color: Colors.teal),
          ),
        ],
      ),
    );
  }

  Widget _buildWeeklyProgress() {
    // Get current date and normalize to midnight for accurate comparison
    final now = DateTime.now();
    final today = DateTime(now.year, now.month, now.day);

    // Calculate days to subtract to get to Monday (weekday: 1=Monday, 7=Sunday)
    // If today is Monday (weekday=1), subtract 0 days
    // If today is Tuesday (weekday=2), subtract 1 day
    // etc.
    final daysToMonday = (today.weekday - 1) % 7;

    // Get the start of the week (Monday) using DateTime arithmetic
    final startOfWeek = today.subtract(Duration(days: daysToMonday));

    // Generate week days starting from Monday
    final List<DateTime> weekDays = List.generate(7, (index) {
      return startOfWeek.add(Duration(days: index));
    });

    // Day abbreviations
    const dayAbbreviations = ['M', 'T', 'W', 'T', 'F', 'S', 'S'];

    // Find today's index in the week (should always be 0-6)
    final todayIndex = weekDays.indexWhere(
      (date) =>
          date.year == today.year &&
          date.month == today.month &&
          date.day == today.day,
    );

    // Calculate completed days (days from Monday up to and including today)
    // If today is Monday, completedDays = 1
    // If today is Tuesday, completedDays = 2
    // etc.
    final int completedDays = todayIndex >= 0 ? todayIndex + 1 : 0;

    // Calculate progress (percentage of week completed)
    final progress = completedDays / 7;

    return Container(
      width: 280, // fixed width to match cards
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.grey[100],
        borderRadius: BorderRadius.circular(12),
        boxShadow: const [
          BoxShadow(color: Colors.black12, blurRadius: 4, offset: Offset(0, 2)),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Icon(Icons.bar_chart, color: Colors.teal),
          const SizedBox(height: 12),
          const Text(
            "Weekly Progress",
            style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
          ),
          const SizedBox(height: 8),
          LinearProgressIndicator(
            value: progress,
            color: Colors.teal,
            backgroundColor: Colors.grey[300],
          ),
          const SizedBox(height: 8),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: weekDays.asMap().entries.map((entry) {
              final index = entry.key;
              final date = entry.value;
              final isToday = todayIndex == index;
              final isPast = index < completedDays;

              return Container(
                key: ValueKey(date),
                child: Column(
                  children: [
                    CircleAvatar(
                      radius: isToday ? 12 : 10,
                      backgroundColor: isToday
                          ? Colors.orange
                          : isPast
                          ? Colors.teal
                          : Colors.grey[400],
                      child: Text(
                        dayAbbreviations[index],
                        style: TextStyle(
                          fontSize: isToday ? 11 : 10,
                          color: Colors.white,
                          fontWeight: isToday
                              ? FontWeight.bold
                              : FontWeight.normal,
                        ),
                      ),
                    ),
                    if (isToday) ...[
                      const SizedBox(height: 2),
                      Container(
                        width: 4,
                        height: 4,
                        decoration: const BoxDecoration(
                          color: Colors.orange,
                          shape: BoxShape.circle,
                        ),
                      ),
                    ],
                  ],
                ),
              );
            }).toList(),
          ),
          const SizedBox(height: 4),
          Text(
            '$completedDays of 7 days completed',
            style: TextStyle(fontSize: 11, color: Colors.grey[600]),
          ),
        ],
      ),
    );
  }

  Widget _buildHabitsSection() {
    final filteredHabits = _filteredHabits;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            const Text(
              "Today's Habits",
              style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold),
            ),
            const Spacer(),
            Text(
              "${_calculateCompletionPercentage()}% Complete",
              style: const TextStyle(color: Colors.teal, fontSize: 14),
            ),
          ],
        ),
        const SizedBox(height: 12),
        Wrap(
          spacing: 8,
          children: [
            _buildFilterChip("All"),
            _buildFilterChip("Mind"),
            _buildFilterChip("Fitness"),
            _buildFilterChip("Learning"),
            _buildFilterChip("Health"),
          ],
        ),
        const SizedBox(height: 12),
        // Show filtered habits as tiles
        if (filteredHabits.isEmpty)
          Padding(
            padding: const EdgeInsets.all(24),
            child: Center(
              child: Text(
                "No habits found in ${_selectedFilter == 'All' ? 'this category' : _selectedFilter} category",
                style: TextStyle(color: Colors.grey.shade600, fontSize: 14),
              ),
            ),
          )
        else
          ..._filteredHabitsWithIndices.map(
            (entry) => _buildHabitTile(entry.key, entry.value),
          ),
        const SizedBox(height: 12),
        // Action buttons row
        Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            TextButton.icon(
              onPressed: _showAddHabitDialog,
              icon: const Icon(Icons.add, color: Colors.teal),
              label: const Text(
                "Add New Habit",
                style: TextStyle(color: Colors.teal),
              ),
            ),
            const SizedBox(width: 16),
            TextButton.icon(
              onPressed: _toggleDeleteMode,
              icon: Icon(
                _isDeleteMode ? Icons.cancel : Icons.delete,
                color: _isDeleteMode ? Colors.red : Colors.teal,
              ),
              label: Text(
                _isDeleteMode ? "Cancel Delete" : "Delete Habit",
                style: TextStyle(
                  color: _isDeleteMode ? Colors.red : Colors.teal,
                ),
              ),
            ),
          ],
        ),
        // Show delete button when in delete mode and habits are selected
        if (_isDeleteMode && _selectedHabitsForDeletion.isNotEmpty)
          Padding(
            padding: const EdgeInsets.only(top: 8),
            child: Center(
              child: ElevatedButton.icon(
                onPressed: _deleteSelectedHabits,
                icon: const Icon(Icons.delete_forever, color: Colors.white),
                label: Text(
                  "Delete Selected (${_selectedHabitsForDeletion.length})",
                  style: const TextStyle(color: Colors.white),
                ),
                style: ElevatedButton.styleFrom(
                  backgroundColor: Colors.red,
                  padding: const EdgeInsets.symmetric(
                    horizontal: 24,
                    vertical: 12,
                  ),
                ),
              ),
            ),
          ),
      ],
    );
  }

  int _calculateCompletionPercentage() {
    final filteredHabits = _filteredHabits;
    if (filteredHabits.isEmpty) return 0;
    int completedCount = filteredHabits.where((h) => h.completed).length;
    return ((completedCount / filteredHabits.length) * 100).round();
  }

  Widget _buildFilterChip(String category) {
    final isSelected = _selectedFilter == category;
    return FilterChip(
      label: Text(category),
      selected: isSelected,
      onSelected: (bool selected) {
        if (selected) {
          setState(() {
            _selectedFilter = category;
            // Clear selections when changing filter in delete mode
            if (_isDeleteMode) {
              _selectedHabitsForDeletion.clear();
            }
          });
        }
      },
      selectedColor: Colors.teal.shade100,
      checkmarkColor: Colors.teal,
      labelStyle: TextStyle(
        color: isSelected ? Colors.teal.shade900 : Colors.black87,
        fontWeight: isSelected ? FontWeight.bold : FontWeight.normal,
      ),
      side: BorderSide(
        color: isSelected ? Colors.teal : Colors.grey.shade300,
        width: isSelected ? 2 : 1,
      ),
    );
  }

  Widget _buildHabitTile(int index, _Habit habit) {
    final isSelected = _selectedHabitsForDeletion.contains(index);
    final isDeleteMode = _isDeleteMode;

    // Determine colors based on habit type (positive = green, negative = red)
    final Color habitColor = habit.isPositive ? Colors.green : Colors.red;
    final Color habitLightColor = habit.isPositive
        ? Colors.green.shade50
        : Colors.red.shade50;
    final Color habitBorderColor = habit.isPositive
        ? Colors.green.shade300
        : Colors.red.shade300;
    final Color habitDarkColor = habit.isPositive
        ? Colors.green.shade700
        : Colors.red.shade700;

    return Container(
      margin: const EdgeInsets.symmetric(vertical: 6),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: isSelected && isDeleteMode
            ? Colors.red.shade50
            : habit.completed
            ? habitLightColor
            : Colors.white,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(
          color: isSelected && isDeleteMode
              ? Colors.red
              : habit.completed
              ? habitColor
              : habitBorderColor,
          width: isSelected && isDeleteMode ? 2 : (habit.completed ? 2 : 1),
        ),
        boxShadow: const [
          BoxShadow(color: Colors.black12, blurRadius: 3, offset: Offset(0, 1)),
        ],
      ),
      child: Row(
        children: [
          // Show selection checkbox in delete mode, otherwise show completion checkbox
          if (isDeleteMode)
            Checkbox(
              value: isSelected,
              activeColor: Colors.red,
              onChanged: (bool? value) {
                setState(() {
                  if (value == true) {
                    _selectedHabitsForDeletion.add(index);
                  } else {
                    _selectedHabitsForDeletion.remove(index);
                  }
                });
              },
            )
          else
            Checkbox(
              value: habit.completed,
              activeColor: habitColor,
              onChanged: (bool? value) async {
                final bool newValue = value ?? false;
                final bool wasCompleted = habit.completed;

                setState(() {
                  final int updatedDays = newValue
                      ? (wasCompleted ? habit.days : habit.days + 1)
                      : habit.days;

                  _habits[index] = _Habit(
                    title: habit.title,
                    category: habit.category,
                    days: updatedDays,
                    completed: newValue,
                    isPositive: habit.isPositive,
                  );
                });

                final List<String> feedbackLines = [];

                if (habit.isPositive) {
                  final change = gamificationStats.registerPositiveHabitChange(
                    wasCompleted: wasCompleted,
                    isCompleted: newValue,
                  );
                  if (change.xpDelta != 0) {
                    final String sign = change.xpDelta > 0 ? '+' : '-';
                    feedbackLines.add('XP $sign${change.xpDelta.abs()}');
                  }
                  if (change.levelDelta != 0) {
                    final String sign = change.levelDelta > 0 ? '+' : '-';
                    feedbackLines.add('Level $sign${change.levelDelta.abs()}');
                  }
                } else {
                  final change = gamificationStats.registerNegativeHabitChange(
                    wasCompleted: wasCompleted,
                    isCompleted: newValue,
                  );
                  if (change.hpDelta != 0) {
                    final String sign = change.hpDelta > 0 ? '+' : '-';
                    feedbackLines.add('HP $sign${change.hpDelta.abs()}');
                  }
                  if (change.levelDelta != 0) {
                    final String sign = change.levelDelta > 0 ? '+' : '-';
                    feedbackLines.add('Level $sign${change.levelDelta.abs()}');
                  }
                  if (change.xpDelta != 0) {
                    final String sign = change.xpDelta > 0 ? '+' : '-';
                    feedbackLines.add('XP $sign${change.xpDelta.abs()}');
                  }
                }

                final statusText = newValue ? 'completed' : 'marked incomplete';
                final baseMessage = "${habit.title} $statusText";
                final snackBarText = feedbackLines.isNotEmpty
                    ? '$baseMessage\n${feedbackLines.join(', ')}'
                    : baseMessage;

                ScaffoldMessenger.of(context).showSnackBar(
                  SnackBar(
                    content: Text(snackBarText),
                    duration: const Duration(seconds: 1),
                  ),
                );
                // Sync change with backend if we have an id
                if (habit.id != null) {
                  try {
                    final resp = await habitService.checkHabit(habit.id!);
                    gamificationStats.updateFromServer(resp);
                  } catch (_) {
                    // ignore network errors for now
                  }
                }
              },
            ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    // Habit type indicator icon
                    Icon(
                      habit.isPositive ? Icons.thumb_up : Icons.thumb_down,
                      size: 16,
                      color: habitColor,
                    ),
                    const SizedBox(width: 4),
                    Expanded(
                      child: Text.rich(
                        TextSpan(
                          text: habit.title,
                          style: TextStyle(
                            fontSize: 16,
                            fontWeight: FontWeight.bold,
                            color: isSelected && isDeleteMode
                                ? Colors.red.shade900
                                : habit.completed
                                ? habitDarkColor
                                : Colors.black,
                          ),
                        ),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 4),
                Text(
                  '${habit.category} • ${habit.days} days',
                  style: TextStyle(
                    fontSize: 12,
                    color: isSelected && isDeleteMode
                        ? Colors.red.shade700
                        : habit.completed
                        ? habitDarkColor.withOpacity(0.7)
                        : Colors.grey,
                  ),
                ),
                // Habit type label
                const SizedBox(height: 2),
                Container(
                  padding: const EdgeInsets.symmetric(
                    horizontal: 6,
                    vertical: 2,
                  ),
                  decoration: BoxDecoration(
                    color: habitColor.withOpacity(0.1),
                    borderRadius: BorderRadius.circular(4),
                    border: Border.all(
                      color: habitColor.withOpacity(0.3),
                      width: 1,
                    ),
                  ),
                  child: Text(
                    habit.isPositive ? 'Positive Habit' : 'Negative Habit',
                    style: TextStyle(
                      fontSize: 10,
                      color: habitDarkColor,
                      fontWeight: FontWeight.w500,
                    ),
                  ),
                ),
              ],
            ),
          ),
          if (habit.completed && !isDeleteMode)
            Icon(
              habit.isPositive
                  ? Icons.local_fire_department
                  : Icons.check_circle,
              color: habit.isPositive ? Colors.orange : habitColor,
            ),
          if (isSelected && isDeleteMode)
            const Icon(Icons.check_circle, color: Colors.red),
        ],
      ),
    );
  }

  void _toggleDeleteMode() {
    setState(() {
      _isDeleteMode = !_isDeleteMode;
      if (!_isDeleteMode) {
        // Clear selections when exiting delete mode
        _selectedHabitsForDeletion.clear();
      }
    });
  }

  void _deleteSelectedHabits() {
    if (_selectedHabitsForDeletion.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text("No habits selected for deletion"),
          duration: Duration(seconds: 2),
        ),
      );
      return;
    }

    showDialog(
      context: context,
      builder: (context) {
        return AlertDialog(
          title: const Text("Delete Habits"),
          content: Text(
            "Are you sure you want to delete ${_selectedHabitsForDeletion.length} habit(s)? This action cannot be undone.",
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.of(context).pop(),
              child: const Text("Cancel"),
            ),
            ElevatedButton(
              onPressed: () async {
                // Attempt server-side delete for each selected habit that has an id.
                final sortedIndices = _selectedHabitsForDeletion.toList()
                  ..sort((a, b) => b.compareTo(a));
                bool anyFailures = false;
                for (final index in sortedIndices) {
                  if (index < 0 || index >= _habits.length) continue;
                  final h = _habits[index];
                  if (h.id != null) {
                    try {
                      await habitService.deleteHabit(h.id!);
                      // on success remove locally
                      setState(() {
                        _habits.removeAt(index);
                      });
                    } catch (e) {
                      anyFailures = true;
                    }
                  } else {
                    // local-only habit: just remove
                    setState(() {
                      _habits.removeAt(index);
                    });
                  }
                }

                setState(() {
                  _selectedHabitsForDeletion.clear();
                  _isDeleteMode = false;
                });

                Navigator.of(context).pop();
                ScaffoldMessenger.of(context).showSnackBar(
                  SnackBar(
                    content: Text(
                      anyFailures
                          ? 'Some deletes failed (offline)'
                          : 'Habits deleted successfully',
                    ),
                    duration: const Duration(seconds: 2),
                  ),
                );
              },
              style: ElevatedButton.styleFrom(backgroundColor: Colors.red),
              child: const Text(
                "Delete",
                style: TextStyle(color: Colors.white),
              ),
            ),
          ],
        );
      },
    );
  }

  void _showAddHabitDialog() {
    final TextEditingController habitTitleController = TextEditingController();
    final TextEditingController daysController = TextEditingController(
      text: "0",
    );
    String selectedCategory = "Mind";
    bool isPositiveHabit = true; // Default to positive habit

    showDialog(
      context: context,
      builder: (context) {
        return AlertDialog(
          title: const Text("Add New Habit"),
          content: StatefulBuilder(
            builder: (context, setStateDialog) {
              return SingleChildScrollView(
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    TextField(
                      controller: habitTitleController,
                      autofocus: true,
                      decoration: const InputDecoration(
                        labelText: "Habit Title",
                        hintText: "Enter habit name",
                      ),
                    ),
                    const SizedBox(height: 16),
                    DropdownButtonFormField<String>(
                      initialValue: selectedCategory,
                      items: const [
                        DropdownMenuItem(value: "Mind", child: Text("Mind")),
                        DropdownMenuItem(
                          value: "Fitness",
                          child: Text("Fitness"),
                        ),
                        DropdownMenuItem(
                          value: "Learning",
                          child: Text("Learning"),
                        ),
                        DropdownMenuItem(
                          value: "Health",
                          child: Text("Health"),
                        ),
                        DropdownMenuItem(value: "Other", child: Text("Other")),
                      ],
                      onChanged: (value) {
                        setStateDialog(() {
                          selectedCategory = value!;
                        });
                      },
                      decoration: const InputDecoration(labelText: "Category"),
                    ),
                    const SizedBox(height: 16),
                    TextField(
                      controller: daysController,
                      keyboardType: TextInputType.number,
                      decoration: const InputDecoration(
                        labelText: "Number of Days",
                        hintText: "Enter number of days",
                        helperText:
                            "How many days have you maintained this habit?",
                      ),
                    ),
                    const SizedBox(height: 16),
                    // Habit type selection
                    const Text(
                      "Habit Type:",
                      style: TextStyle(
                        fontSize: 14,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                    const SizedBox(height: 8),
                    Row(
                      children: [
                        Expanded(
                          child: GestureDetector(
                            onTap: () {
                              setStateDialog(() {
                                isPositiveHabit = true;
                              });
                            },
                            child: Container(
                              padding: const EdgeInsets.all(12),
                              decoration: BoxDecoration(
                                color: isPositiveHabit
                                    ? Colors.green.shade50
                                    : Colors.grey.shade100,
                                borderRadius: BorderRadius.circular(8),
                                border: Border.all(
                                  color: isPositiveHabit
                                      ? Colors.green
                                      : Colors.grey.shade300,
                                  width: isPositiveHabit ? 2 : 1,
                                ),
                              ),
                              child: Row(
                                mainAxisAlignment: MainAxisAlignment.center,
                                children: [
                                  Icon(
                                    Icons.thumb_up,
                                    color: isPositiveHabit
                                        ? Colors.green
                                        : Colors.grey,
                                    size: 20,
                                  ),
                                  const SizedBox(width: 8),
                                  Text(
                                    "Positive",
                                    style: TextStyle(
                                      color: isPositiveHabit
                                          ? Colors.green.shade700
                                          : Colors.grey,
                                      fontWeight: isPositiveHabit
                                          ? FontWeight.bold
                                          : FontWeight.normal,
                                    ),
                                  ),
                                ],
                              ),
                            ),
                          ),
                        ),
                        const SizedBox(width: 12),
                        Expanded(
                          child: GestureDetector(
                            onTap: () {
                              setStateDialog(() {
                                isPositiveHabit = false;
                              });
                            },
                            child: Container(
                              padding: const EdgeInsets.all(12),
                              decoration: BoxDecoration(
                                color: !isPositiveHabit
                                    ? Colors.red.shade50
                                    : Colors.grey.shade100,
                                borderRadius: BorderRadius.circular(8),
                                border: Border.all(
                                  color: !isPositiveHabit
                                      ? Colors.red
                                      : Colors.grey.shade300,
                                  width: !isPositiveHabit ? 2 : 1,
                                ),
                              ),
                              child: Row(
                                mainAxisAlignment: MainAxisAlignment.center,
                                children: [
                                  Icon(
                                    Icons.thumb_down,
                                    color: !isPositiveHabit
                                        ? Colors.red
                                        : Colors.grey,
                                    size: 20,
                                  ),
                                  const SizedBox(width: 8),
                                  Text(
                                    "Negative",
                                    style: TextStyle(
                                      color: !isPositiveHabit
                                          ? Colors.red.shade700
                                          : Colors.grey,
                                      fontWeight: !isPositiveHabit
                                          ? FontWeight.bold
                                          : FontWeight.normal,
                                    ),
                                  ),
                                ],
                              ),
                            ),
                          ),
                        ),
                      ],
                    ),
                  ],
                ),
              );
            },
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.of(context).pop(),
              child: const Text("Cancel"),
            ),
            ElevatedButton(
              onPressed: () async {
                final newTitle = habitTitleController.text.trim();
                if (newTitle.isEmpty) {
                  ScaffoldMessenger.of(context).showSnackBar(
                    const SnackBar(
                      content: Text("Habit title can't be empty!"),
                    ),
                  );
                  return;
                }

                // Parse and validate number of days
                final daysText = daysController.text.trim();
                int days = 0;
                if (daysText.isNotEmpty) {
                  final parsedDays = int.tryParse(daysText);
                  if (parsedDays == null || parsedDays < 0) {
                    ScaffoldMessenger.of(context).showSnackBar(
                      const SnackBar(
                        content: Text(
                          "Please enter a valid number of days (0 or greater)",
                        ),
                      ),
                    );
                    return;
                  }
                  days = parsedDays;
                }

                try {
                  final created = await habitService.createHabit(
                    title: newTitle,
                    category: selectedCategory,
                    days: days,
                    isPositive: isPositiveHabit,
                  );

                  setState(() {
                    _habits.add(
                      _Habit(
                        id: (created['id'] is int)
                            ? created['id'] as int
                            : (created['habit_id'] is int
                                  ? created['habit_id'] as int
                                  : null),
                        title: newTitle,
                        category: selectedCategory,
                        days: days,
                        completed: false,
                        isPositive: isPositiveHabit,
                      ),
                    );
                  });
                } catch (e) {
                  ScaffoldMessenger.of(context).showSnackBar(
                    const SnackBar(
                      content: Text('Failed to create habit (network)'),
                    ),
                  );
                }
                Navigator.of(context).pop();
              },
              child: const Text("Add"),
            ),
          ],
        );
      },
    );
  }

  String _getAppBarTitle() {
    switch (_selectedIndex) {
      case 0:
        return 'Home';
      case 1:
        return 'AI Assistant';
      case 2:
        return 'Journal';
      case 3:
        return 'Gamification';
      default:
        return 'Home';
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text(_getAppBarTitle()),
        backgroundColor: Colors.teal,
      ),
      drawer: Drawer(
        child: ListView(
          padding: EdgeInsets.zero,
          children: [
            DrawerHeader(
              decoration: const BoxDecoration(color: Colors.teal),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const CircleAvatar(
                    radius: 32,
                    backgroundImage: NetworkImage(
                      'https://randomuser.me/api/portraits/women/44.jpg',
                    ),
                  ),
                  const SizedBox(height: 12),
                  Text(
                    _currentUserFullName(),
                    style: const TextStyle(color: Colors.white, fontSize: 18),
                  ),
                  Text(
                    _currentUserEmail(),
                    style: const TextStyle(color: Colors.white70, fontSize: 14),
                  ),
                ],
              ),
            ),
            ListTile(
              leading: const Icon(Icons.home),
              title: const Text('Home'),
              onTap: () => Navigator.pop(context),
            ),
            ListTile(
              leading: const Icon(Icons.account_circle),
              title: const Text('Profile'),
              onTap: () => Navigator.pop(context),
            ),
            ListTile(
              leading: const Icon(Icons.settings),
              title: const Text('Settings'),
              onTap: () => Navigator.pop(context),
            ),
            ListTile(
              leading: const Icon(Icons.logout),
              title: const Text('Logout'),
              onTap: _handleLogout,
            ),
          ],
        ),
      ),
      body: _pages[_selectedIndex],
      bottomNavigationBar: BottomNavigationBar(
        currentIndex: _selectedIndex,
        onTap: _navigateBottomBar,
        type: BottomNavigationBarType.fixed,
        backgroundColor: Colors.teal,
        selectedItemColor: Colors.white,
        unselectedItemColor: Colors.white54,
        items: const [
          BottomNavigationBarItem(icon: Icon(Icons.home), label: 'Home'),
          BottomNavigationBarItem(
            icon: Icon(Icons.smart_toy),
            label: 'AI Assistant',
          ),
          BottomNavigationBarItem(icon: Icon(Icons.book), label: 'Journal'),
          BottomNavigationBarItem(
            icon: Icon(Icons.star),
            label: 'Gamification',
          ),
        ],
      ),
    );
  }

  Widget _buildCalendarSection() {
    final selectedTasks = _getTasksForDay(_selectedDay);
    final progressEntry = _getProgressForDay(_selectedDay);

    return Container(
      margin: const EdgeInsets.only(top: 24),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        boxShadow: const [
          BoxShadow(color: Colors.black12, blurRadius: 8, offset: Offset(0, 4)),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(Icons.calendar_today, color: Colors.teal),
              const SizedBox(width: 8),
              Expanded(
                child: Text(
                  'Habit Calendar & To-Do',
                  style: Theme.of(context).textTheme.titleMedium?.copyWith(
                    fontWeight: FontWeight.bold,
                  ),
                ),
              ),
              Text(
                _formatDate(_selectedDay),
                style: const TextStyle(color: Colors.grey),
              ),
            ],
          ),
          const SizedBox(height: 16),
          TableCalendar(
            firstDay: DateTime.utc(2020, 1, 1),
            lastDay: DateTime.utc(2100, 12, 31),
            focusedDay: _focusedDay,
            selectedDayPredicate: (day) => isSameDay(day, _selectedDay),
            startingDayOfWeek: StartingDayOfWeek.monday,
            calendarFormat: CalendarFormat.month,
            onDaySelected: (selectedDay, focusedDay) {
              setState(() {
                _selectedDay = _normalizeDate(selectedDay);
                _focusedDay = focusedDay;
              });
            },
            headerStyle: const HeaderStyle(
              formatButtonVisible: false,
              titleCentered: true,
            ),
            calendarStyle: CalendarStyle(
              todayDecoration: BoxDecoration(
                color: Colors.teal.shade100,
                shape: BoxShape.circle,
              ),
              selectedDecoration: const BoxDecoration(
                color: Colors.teal,
                shape: BoxShape.circle,
              ),
              selectedTextStyle: const TextStyle(color: Colors.white),
              markerDecoration: BoxDecoration(
                color: Colors.orange.shade400,
                shape: BoxShape.circle,
              ),
            ),
            eventLoader: _getCalendarEventsForDay,
            calendarBuilders: CalendarBuilders(
              markerBuilder: (context, date, events) {
                if (events.isEmpty) return null;
                return Positioned(
                  bottom: 6,
                  child: Row(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: events.map((event) {
                      Color color;
                      if (event == 'tasks') {
                        color = Colors.blueAccent;
                      } else {
                        color = Colors.teal;
                      }
                      return Container(
                        width: 6,
                        height: 6,
                        margin: const EdgeInsets.symmetric(horizontal: 1),
                        decoration: BoxDecoration(
                          color: color,
                          shape: BoxShape.circle,
                        ),
                      );
                    }).toList(),
                  ),
                );
              },
            ),
          ),
          const SizedBox(height: 16),
          _buildProgressCard(progressEntry),
          const SizedBox(height: 16),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              const Text(
                'Tasks & Deadlines',
                style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
              ),
              TextButton.icon(
                onPressed:
                    _showAddCalendarTaskDialog, // ✅ make sure this method exists
                icon: const Icon(Icons.add),
                label: const Text('Add Task'),
              ),
            ],
          ),

          selectedTasks.isEmpty
              ? Container(
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    color: Colors.grey.shade100,
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: const Text(
                    'No tasks for this date. Tap "Add Task" to plan your habits.',
                    style: TextStyle(color: Colors.grey),
                  ),
                )
              : ListView.builder(
                  physics: const NeverScrollableScrollPhysics(),
                  shrinkWrap: true,
                  itemCount: selectedTasks.length,
                  itemBuilder: (context, index) {
                    final task = selectedTasks[index];
                    final deadlineText = _formatTime(task.deadline);
                    return Card(
                      margin: const EdgeInsets.symmetric(vertical: 6),
                      child: ListTile(
                        leading: Checkbox(
                          value: task.completed,
                          onChanged: (_) =>
                              _toggleTaskCompleted(_selectedDay, index),
                        ),
                        title: Text(
                          task.title,
                          style: TextStyle(
                            decoration: task.completed
                                ? TextDecoration.lineThrough
                                : TextDecoration.none,
                          ),
                        ),
                        subtitle: deadlineText != null
                            ? Text('Deadline: $deadlineText')
                            : null,
                        trailing: IconButton(
                          icon: const Icon(Icons.delete_outline),
                          onPressed: () => _deleteTask(_selectedDay, index),
                        ),
                      ),
                    );
                  },
                ),
        ],
      ),
    );
  }

  Widget _buildProgressCard(_DailyProgressEntry? entry) {
    if (entry == null) {
      return Container(
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: Colors.teal.shade50,
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: Colors.teal.shade100),
        ),
        child: Row(
          children: [
            const Icon(Icons.insights, color: Colors.teal),
            const SizedBox(width: 12),
            Expanded(
              child: Text(
                'No progress logged for this date yet. Tap the button below to capture your current habit progress.',
                style: const TextStyle(color: Colors.teal),
              ),
            ),
            ElevatedButton(
              onPressed: _logProgressForSelectedDay,
              child: const Text('Log Progress'),
            ),
          ],
        ),
      );
    }

    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.teal.shade600,
        borderRadius: BorderRadius.circular(12),
        boxShadow: const [
          BoxShadow(color: Colors.black12, blurRadius: 6, offset: Offset(0, 3)),
        ],
      ),
      child: Row(
        children: [
          const Icon(Icons.show_chart, color: Colors.white),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  '${entry.completionPercentage}% of habits completed',
                  style: const TextStyle(
                    color: Colors.white,
                    fontSize: 16,
                    fontWeight: FontWeight.bold,
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  '${entry.completedHabits}/${entry.totalHabits} habits completed',
                  style: const TextStyle(color: Colors.white70),
                ),
                const SizedBox(height: 4),
                Text(
                  'Logged on ${_formatDate(entry.loggedAt)}',
                  style: const TextStyle(color: Colors.white54, fontSize: 12),
                ),
              ],
            ),
          ),
          ElevatedButton(
            onPressed: _logProgressForSelectedDay,
            style: ElevatedButton.styleFrom(
              backgroundColor: Colors.white,
              foregroundColor: Colors.teal,
            ),
            child: const Text('Update'),
          ),
        ],
      ),
    );
  }

  Future<void> _showAddCalendarTaskDialog() async {
    final TextEditingController taskController = TextEditingController();
    TimeOfDay? selectedTime;

    await showDialog(
      context: context,
      builder: (context) {
        return AlertDialog(
          title: const Text('Add Task'),
          content: StatefulBuilder(
            builder: (context, setStateDialog) {
              return Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  TextField(
                    controller: taskController,
                    autofocus: true,
                    decoration: const InputDecoration(
                      labelText: 'Task Title',
                      hintText: 'Enter a task or goal',
                    ),
                  ),
                  const SizedBox(height: 16),
                  Row(
                    children: [
                      Expanded(
                        child: Text(
                          selectedTime != null
                              ? 'Deadline: ${selectedTime!.format(context)}'
                              : 'No deadline selected',
                        ),
                      ),
                      TextButton.icon(
                        onPressed: () async {
                          final TimeOfDay? picked = await showTimePicker(
                            context: context,
                            initialTime: TimeOfDay.now(),
                          );
                          if (picked != null) {
                            setStateDialog(() {
                              selectedTime = picked;
                            });
                          }
                        },
                        icon: const Icon(Icons.schedule),
                        label: const Text('Set time'),
                      ),
                    ],
                  ),
                ],
              );
            },
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.of(context).pop(),
              child: const Text('Cancel'),
            ),
            ElevatedButton(
              onPressed: () {
                final String title = taskController.text.trim();
                if (title.isEmpty) {
                  ScaffoldMessenger.of(context).showSnackBar(
                    const SnackBar(content: Text('Task title cannot be empty')),
                  );
                  return;
                }
                (() async {
                  final DateTime normalized = _normalizeDate(_selectedDay);
                  final DateTime? deadline = selectedTime != null
                      ? DateTime(
                          normalized.year,
                          normalized.month,
                          normalized.day,
                          selectedTime!.hour,
                          selectedTime!.minute,
                        )
                      : null;

                  try {
                    final created = await habitService.createTask(
                      title: title,
                      deadline: deadline,
                    );

                    final int? tid = (created['id'] is int)
                        ? created['id'] as int
                        : (created['task_id'] is int
                              ? created['task_id'] as int
                              : null);

                    final tasks =
                        List<_CalendarTask>.from(_getTasksForDay(normalized))
                          ..add(
                            _CalendarTask(
                              id: tid,
                              title: title,
                              deadline: deadline,
                              completed: false,
                            ),
                          );

                    setState(() {
                      _setTasksForDay(normalized, tasks);
                    });
                  } catch (e) {
                    // fallback to local-only add on failure
                    final tasks =
                        List<_CalendarTask>.from(_getTasksForDay(_selectedDay))
                          ..add(
                            _CalendarTask(
                              id: null,
                              title: title,
                              deadline: selectedTime != null
                                  ? DateTime(
                                      _selectedDay.year,
                                      _selectedDay.month,
                                      _selectedDay.day,
                                      selectedTime!.hour,
                                      selectedTime!.minute,
                                    )
                                  : null,
                              completed: false,
                            ),
                          );

                    setState(() {
                      _setTasksForDay(_selectedDay, tasks);
                    });
                  }

                  Navigator.of(context).pop();
                })();
              },
              child: const Text('Add'),
            ),
          ],
        );
      },
    );
  }

  void _toggleTaskCompleted(DateTime day, int taskIndex) {
    final List<_CalendarTask> tasks = List<_CalendarTask>.from(
      _getTasksForDay(day),
    );
    if (taskIndex < 0 || taskIndex >= tasks.length) return;

    final task = tasks[taskIndex];
    final bool wasCompleted = task.completed;
    final bool newCompleted = !wasCompleted;

    // Update task completion status
    tasks[taskIndex] = _CalendarTask(
      id: task.id,
      title: task.title,
      deadline: task.deadline,
      completed: newCompleted,
    );

    setState(() {
      _setTasksForDay(day, tasks);
    });

    // Handle rewards/penalties based on deadline
    if (newCompleted && !wasCompleted) {
      // Task is being marked as completed
      final DateTime now = DateTime.now();
      final bool hasDeadline = task.deadline != null;
      final bool beforeDeadline = hasDeadline && now.isBefore(task.deadline!);

      if (hasDeadline && beforeDeadline) {
        // Completed before deadline: Award XP
        gamificationStats.awardTaskCompletionXP();
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Task completed on time! You gained XP🎉'),
            duration: const Duration(seconds: 2),
            backgroundColor: Colors.green,
          ),
        );
      } else if (hasDeadline && !beforeDeadline) {
        // Completed after deadline: No reward, but also no penalty (already missed)
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text(
              'Task completed, but deadline has passed. No reward.',
            ),
            duration: Duration(seconds: 2),
            backgroundColor: Colors.orange,
          ),
        );
      } else {
        // No deadline: Just mark as completed
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Task "${task.title}" marked as completed'),
            duration: const Duration(seconds: 1),
          ),
        );
      }
      // Sync completion with backend if task has id
      if (task.id != null) {
        (() async {
          try {
            final resp = await habitService.completeTask(task.id!);
            gamificationStats.updateFromServer(resp);
          } catch (_) {
            // ignore network errors
          }
        })();
      }
    } else if (!newCompleted && wasCompleted) {
      // Task is being unmarked - no action needed
    }
  }

  void _deleteTask(DateTime day, int taskIndex) {
    final List<_CalendarTask> tasks = List<_CalendarTask>.from(
      _getTasksForDay(day),
    );
    if (taskIndex < 0 || taskIndex >= tasks.length) return;

    final _CalendarTask task = tasks[taskIndex];
    // If this task has a server id, request deletion; otherwise just remove locally
    if (task.id != null) {
      (() async {
        try {
          await habitService.deleteTask(task.id!);
          // On success remove locally
          setState(() {
            tasks.removeAt(taskIndex);
            _setTasksForDay(day, tasks);
          });
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(
              content: Text('Task deleted'),
              duration: Duration(seconds: 2),
            ),
          );
        } catch (e) {
          // network or server error - fallback to local removal
          setState(() {
            tasks.removeAt(taskIndex);
            _setTasksForDay(day, tasks);
          });
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(
              content: Text('Task deleted locally (offline)'),
              duration: Duration(seconds: 2),
            ),
          );
        }
      })();
    } else {
      tasks.removeAt(taskIndex);
      setState(() {
        _setTasksForDay(day, tasks);
      });
    }
  }

  void _logProgressForSelectedDay() {
    final DateTime normalized = _normalizeDate(_selectedDay);
    final int totalHabits = _habits.length;
    final int completedHabits = _habits
        .where((habit) => habit.completed)
        .length;

    final entry = _DailyProgressEntry(
      loggedAt: DateTime.now(),
      totalHabits: totalHabits,
      completedHabits: completedHabits,
    );

    setState(() {
      _setProgressForDay(normalized, entry);
    });

    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(
          'Progress saved for ${_formatDate(normalized)} (${entry.completionPercentage}% completed)',
        ),
        duration: const Duration(seconds: 2),
      ),
    );
  }
}

// Helper classes for calendar tasks and progress
class _CalendarTask {
  final int? id;
  final String title;
  final DateTime? deadline;
  final bool completed;

  _CalendarTask({
    this.id,
    required this.title,
    required this.deadline,
    required this.completed,
  });
}

class _DailyProgressEntry {
  final DateTime loggedAt;
  final int totalHabits;
  final int completedHabits;

  _DailyProgressEntry({
    required this.loggedAt,
    required this.totalHabits,
    required this.completedHabits,
  });

  int get completionPercentage {
    if (totalHabits == 0) return 0;
    return ((completedHabits / totalHabits) * 100).round();
  }
}

// Helper Habit class to store habit data
class _Habit {
  final int? id;
  final String title;
  final String category;
  final int days;
  final bool completed;
  final bool
  isPositive; // true for positive habits (green), false for negative habits (red)

  _Habit({
    this.id,
    required this.title,
    required this.category,
    required this.days,
    required this.completed,
    required this.isPositive,
  });
}
