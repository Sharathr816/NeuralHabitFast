import 'dart:math';

import 'package:flutter/material.dart';
import 'package:flutter_application_1/models/gamification_stats.dart';
import 'package:flutter_application_1/services/habit_service.dart';

class GamificationPage extends StatefulWidget {
  const GamificationPage({super.key});

  @override
  State<GamificationPage> createState() => _GamificationPageState();
}

class _GamificationPageState extends State<GamificationPage> {
  late final GamificationStats stats;
  final Random _random = Random();

  @override
  void initState() {
    super.initState();
    stats = gamificationStats;
    stats.addListener(_onStatsChanged);
    // Sync initial stats from backend
    WidgetsBinding.instance.addPostFrameCallback((_) async {
      try {
        final server = await habitService.fetchStats();
        gamificationStats.updateFromServer(server);
      } catch (_) {}
    });
  }

  void _onStatsChanged() {
    if (mounted) {
      setState(() {});
    }
  }

  @override
  void dispose() {
    stats.removeListener(_onStatsChanged);
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.grey[100],
      appBar: AppBar(
        title: const Row(
          children: [
            Icon(Icons.stars, color: Colors.white),
            SizedBox(width: 8),
            Text('Neural arsenal'),
          ],
        ),
        backgroundColor: Colors.teal,
        elevation: 0,
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Level and XP Card
            _buildLevelCard(),
            const SizedBox(height: 16),

            // Health Points Card
            _buildHealthPointsCard(),
            const SizedBox(height: 16),

            // Health Mini Game
            _buildHealthMiniGameCard(),
            const SizedBox(height: 16),

            // Stats Grid
            _buildStatsGrid(),
            const SizedBox(height: 16),

            // Streak Card
            _buildStreakCard(),
            const SizedBox(height: 16),

            // Achievements Section
            _buildAchievementsSection(),
            const SizedBox(height: 16),
          ],
        ),
      ),
    );
  }

  Widget _buildLevelCard() {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          colors: [Colors.purple.shade400, Colors.purple.shade600],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        borderRadius: BorderRadius.circular(16),
        boxShadow: [
          BoxShadow(
            color: Colors.purple.withOpacity(0.3),
            blurRadius: 8,
            offset: const Offset(0, 4),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text(
                    'Level',
                    style: TextStyle(
                      color: Colors.white70,
                      fontSize: 14,
                      fontWeight: FontWeight.w500,
                    ),
                  ),
                  Text(
                    '${stats.currentLevel}',
                    style: const TextStyle(
                      color: Colors.white,
                      fontSize: 36,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                ],
              ),
              Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: Colors.white.withOpacity(0.2),
                  shape: BoxShape.circle,
                ),
                child: const Icon(Icons.stars, color: Colors.white, size: 32),
              ),
            ],
          ),
          const SizedBox(height: 20),
          // XP Progress Bar
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Text(
                    'XP: ${stats.currentXP}',
                    style: const TextStyle(
                      color: Colors.white,
                      fontSize: 14,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                  Text(
                    '${stats.xpForNextLevel} XP to Level ${stats.currentLevel + 1}',
                    style: const TextStyle(color: Colors.white70, fontSize: 12),
                  ),
                ],
              ),
              const SizedBox(height: 8),
              Stack(
                children: [
                  Container(
                    height: 20,
                    decoration: BoxDecoration(
                      color: Colors.black.withOpacity(0.2),
                      borderRadius: BorderRadius.circular(10),
                    ),
                  ),
                  FractionallySizedBox(
                    widthFactor: stats.xpProgressPercentage.clamp(0.0, 1.0),
                    child: Container(
                      height: 20,
                      decoration: BoxDecoration(
                        gradient: LinearGradient(
                          colors: [
                            Colors.amber.shade400,
                            Colors.amber.shade600,
                          ],
                        ),
                        borderRadius: BorderRadius.circular(10),
                        boxShadow: [
                          BoxShadow(
                            color: Colors.amber.withOpacity(0.5),
                            blurRadius: 4,
                            offset: const Offset(0, 2),
                          ),
                        ],
                      ),
                    ),
                  ),
                  Container(
                    height: 20,
                    alignment: Alignment.center,
                    child: Text(
                      '${stats.xpProgress} / ${stats.xpNeeded} XP',
                      style: const TextStyle(
                        color: Colors.white,
                        fontSize: 11,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                  ),
                ],
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildHealthPointsCard() {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          colors: [Colors.red.shade400, Colors.red.shade600],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        borderRadius: BorderRadius.circular(16),
        boxShadow: [
          BoxShadow(
            color: Colors.red.withOpacity(0.3),
            blurRadius: 8,
            offset: const Offset(0, 4),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              const Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'Health Points',
                    style: TextStyle(
                      color: Colors.white70,
                      fontSize: 14,
                      fontWeight: FontWeight.w500,
                    ),
                  ),
                  Text(
                    'HP',
                    style: TextStyle(
                      color: Colors.white,
                      fontSize: 24,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                ],
              ),
              Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: Colors.white.withOpacity(0.2),
                  shape: BoxShape.circle,
                ),
                child: const Icon(
                  Icons.favorite,
                  color: Colors.white,
                  size: 32,
                ),
              ),
            ],
          ),
          const SizedBox(height: 20),
          // HP Progress
          Row(
            children: [
              Expanded(
                child: Stack(
                  children: [
                    Container(
                      height: 30,
                      decoration: BoxDecoration(
                        color: Colors.black.withOpacity(0.2),
                        borderRadius: BorderRadius.circular(15),
                      ),
                    ),
                    FractionallySizedBox(
                      widthFactor: (stats.currentHP / 100).clamp(0.0, 1.0),
                      child: Container(
                        height: 30,
                        decoration: BoxDecoration(
                          gradient: LinearGradient(
                            colors: [
                              Colors.green.shade400,
                              Colors.green.shade600,
                            ],
                          ),
                          borderRadius: BorderRadius.circular(15),
                          boxShadow: [
                            BoxShadow(
                              color: Colors.green.withOpacity(0.5),
                              blurRadius: 4,
                              offset: const Offset(0, 2),
                            ),
                          ],
                        ),
                      ),
                    ),
                    Container(
                      height: 30,
                      alignment: Alignment.center,
                      child: Text(
                        '${stats.currentHP} / 100 HP',
                        style: const TextStyle(
                          color: Colors.white,
                          fontSize: 14,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(width: 12),
              Container(
                padding: const EdgeInsets.symmetric(
                  horizontal: 12,
                  vertical: 8,
                ),
                decoration: BoxDecoration(
                  color: Colors.white.withOpacity(0.2),
                  borderRadius: BorderRadius.circular(20),
                ),
                child: Text(
                  _getHPStatus(stats.currentHP),
                  style: const TextStyle(
                    color: Colors.white,
                    fontSize: 12,
                    fontWeight: FontWeight.bold,
                  ),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildHealthMiniGameCard() {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          colors: [Colors.cyan.shade400, Colors.cyan.shade600],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        borderRadius: BorderRadius.circular(16),
        boxShadow: [
          BoxShadow(
            color: Colors.cyan.withOpacity(0.3),
            blurRadius: 8,
            offset: const Offset(0, 4),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: Colors.white.withOpacity(0.2),
                  shape: BoxShape.circle,
                ),
                child: const Icon(
                  Icons.videogame_asset,
                  color: Colors.white,
                  size: 28,
                ),
              ),
              const SizedBox(width: 12),
              const Expanded(
                child: Text(
                  'Health Potion Mini-Game',
                  style: TextStyle(
                    color: Colors.white,
                    fontSize: 20,
                    fontWeight: FontWeight.bold,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          Text(
            _getGameDescriptionText(),
            style: const TextStyle(
              color: Colors.white70,
              fontSize: 13,
              height: 1.4,
            ),
          ),
          const SizedBox(height: 16),
          Align(
            alignment: Alignment.centerLeft,
            child: ElevatedButton.icon(
              onPressed: _canPlayGame() ? _startHealthMiniGame : null,
              style: ElevatedButton.styleFrom(
                backgroundColor: Colors.white,
                foregroundColor: Colors.cyan.shade700,
                padding: const EdgeInsets.symmetric(
                  horizontal: 20,
                  vertical: 12,
                ),
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(24),
                ),
              ),
              icon: const Icon(Icons.health_and_safety),
              label: Text(
                _getGameButtonText(),
                style: const TextStyle(fontWeight: FontWeight.bold),
              ),
            ),
          ),
        ],
      ),
    );
  }

  bool _canPlayGame() {
    if (stats.currentHP >= 100) return false;
    return stats.canPlayMiniGameForLevel();
  }

  String _getGameDescriptionText() {
    if (stats.currentHP >= 100) {
      return 'Your HP is maxed out! Keep it up or replay later when you need a boost.';
    }

    final remaining = stats.getRemainingPlaysForLevel();
    if (remaining == 0) {
      return 'You\'ve reached the play limit for this level. Level up to unlock more plays.';
    }

    return 'Pick the glowing potion to earn an instant +10 HP boost. You can only gain health up to 100 HP.\n\nRemaining plays for this level: $remaining/3';
  }

  String _getGameButtonText() {
    if (!_canPlayGame()) {
      if (stats.currentHP >= 100) {
        return 'HP Full';
      }
      return 'Limit Reached';
    }
    return 'Play Health Game';
  }

  Future<void> _startHealthMiniGame() async {
    // Check again before starting (in case state changed)
    if (!_canPlayGame()) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            stats.currentHP >= 100
                ? 'Your HP is full.'
                : 'Mini-game play limit reached for this level.',
          ),
          duration: const Duration(seconds: 2),
        ),
      );
      return;
    }

    final _HealthGameResult? result = await _showHealthMiniGameDialog();
    if (!mounted || result == null) return;

    // Record the game play on the server (includes whether the user won) and refresh stats
    try {
      final serverResp = await habitService.playHealthPotion(won: result.won);
      gamificationStats.updateFromServer(serverResp);
    } catch (_) {
      // Offline: do NOT record a local play count (to avoid enabling replay after reload).
      // Apply local HP award so user gets immediate feedback, but server must confirm plays.
      if (result.won) {
        final local = stats.awardHealth(10);
        if (local.hpDelta > 0) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
              content: Text(
                'You found a potion! +${local.hpDelta} HP (local, offline)',
              ),
              duration: const Duration(seconds: 2),
            ),
          );
        }
      } else {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Played offline; result will sync when online'),
            duration: Duration(seconds: 2),
          ),
        );
      }
    }

    if (result.message.isNotEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(result.message),
          duration: const Duration(seconds: 2),
        ),
      );
    }
  }

  Future<_HealthGameResult?> _showHealthMiniGameDialog() async {
    final int winningIndex = _random.nextInt(3);
    int? selectedIndex;
    bool hasPlayed = false;
    String statusMessage = 'Pick a potion to discover a healing elixir!';
    // no local HP mutation here; server will apply +10 HP on win

    return showDialog<_HealthGameResult?>(
      context: context,
      barrierDismissible: false,
      builder: (dialogContext) {
        return StatefulBuilder(
          builder: (context, setStateDialog) {
            void handleSelect(int index) {
              if (hasPlayed) return;

              selectedIndex = index;
              final bool isWinner = index == winningIndex;

              if (isWinner) {
                // mark win locally for UI; server will award +10 HP when play is submitted
                statusMessage =
                    'You found a healing potion! Claim +10 HP when you submit.';
              } else {
                statusMessage = 'That potion was empty. Better luck next time!';
              }

              hasPlayed = true;
              setStateDialog(() {});
            }

            return AlertDialog(
              title: const Text('Health Potion Hunt'),
              content: SizedBox(
                width: 320,
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Text(
                      statusMessage,
                      textAlign: TextAlign.center,
                      style: const TextStyle(fontSize: 14, height: 1.4),
                    ),
                    const SizedBox(height: 16),
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceEvenly,
                      children: List.generate(3, (index) {
                        final bool isWinner = index == winningIndex;
                        final bool isSelected = selectedIndex == index;

                        Color bgColor;
                        IconData icon;
                        Color iconColor;

                        if (hasPlayed) {
                          if (isWinner) {
                            bgColor = Colors.green.shade500;
                            icon = Icons.health_and_safety;
                            iconColor = Colors.white;
                          } else if (isSelected) {
                            bgColor = Colors.red.shade400;
                            icon = Icons.close;
                            iconColor = Colors.white;
                          } else {
                            bgColor = Colors.grey.shade400;
                            icon = Icons.local_drink;
                            iconColor = Colors.white70;
                          }
                        } else {
                          bgColor = isSelected
                              ? Colors.cyan.shade400
                              : Colors.cyan.shade200;
                          icon = Icons.help_outline;
                          iconColor = Colors.white;
                        }

                        return GestureDetector(
                          onTap: hasPlayed ? null : () => handleSelect(index),
                          child: AnimatedContainer(
                            duration: const Duration(milliseconds: 250),
                            width: 64,
                            height: 64,
                            decoration: BoxDecoration(
                              color: bgColor,
                              borderRadius: BorderRadius.circular(16),
                              boxShadow: [
                                if (isSelected)
                                  const BoxShadow(
                                    color: Colors.black26,
                                    blurRadius: 6,
                                    offset: Offset(0, 3),
                                  ),
                              ],
                            ),
                            child: Icon(icon, color: iconColor, size: 30),
                          ),
                        );
                      }),
                    ),
                  ],
                ),
              ),
              actions: [
                TextButton(
                  onPressed: () {
                    Navigator.of(dialogContext).pop(
                      hasPlayed
                          ? _HealthGameResult(
                              won:
                                  selectedIndex != null &&
                                  selectedIndex == winningIndex,
                              message: statusMessage,
                            )
                          : null,
                    );
                  },
                  child: Text(hasPlayed ? 'Close' : 'Cancel'),
                ),
              ],
            );
          },
        );
      },
    );
  }

  String _getHPStatus(int hp) {
    if (hp >= 80) return 'Excellent';
    if (hp >= 60) return 'Good';
    if (hp >= 40) return 'Fair';
    return 'Low';
  }

  Widget _buildStatsGrid() {
    return Row(
      children: [
        Expanded(
          child: _buildStatCard(
            icon: Icons.check_circle,
            iconColor: Colors.green,
            title: 'Completed',
            value: '${stats.totalHabitsCompleted}',
            subtitle: 'Total Habits',
            gradient: [Colors.green.shade400, Colors.green.shade600],
          ),
        ),
        const SizedBox(width: 12),
        Expanded(
          child: _buildStatCard(
            icon: Icons.thumb_up,
            iconColor: Colors.blue,
            title: 'Positive',
            value: '${stats.positiveHabitsCompleted}',
            subtitle: 'Good Habits',
            gradient: [Colors.blue.shade400, Colors.blue.shade600],
          ),
        ),
      ],
    );
  }

  Widget _buildStatCard({
    required IconData icon,
    required Color iconColor,
    required String title,
    required String value,
    required String subtitle,
    required List<Color> gradient,
  }) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          colors: gradient,
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        borderRadius: BorderRadius.circular(12),
        boxShadow: [
          BoxShadow(
            color: gradient[0].withOpacity(0.3),
            blurRadius: 6,
            offset: const Offset(0, 3),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(icon, color: Colors.white, size: 24),
          const SizedBox(height: 12),
          Text(
            value,
            style: const TextStyle(
              color: Colors.white,
              fontSize: 24,
              fontWeight: FontWeight.bold,
            ),
          ),
          const SizedBox(height: 4),
          Text(
            title,
            style: const TextStyle(color: Colors.white70, fontSize: 12),
          ),
          Text(
            subtitle,
            style: const TextStyle(color: Colors.white70, fontSize: 10),
          ),
        ],
      ),
    );
  }

  Widget _buildStreakCard() {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          colors: [Colors.orange.shade400, Colors.orange.shade600],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        borderRadius: BorderRadius.circular(16),
        boxShadow: [
          BoxShadow(
            color: Colors.orange.withOpacity(0.3),
            blurRadius: 8,
            offset: const Offset(0, 4),
          ),
        ],
      ),
      child: Row(
        children: [
          Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: Colors.white.withOpacity(0.2),
              shape: BoxShape.circle,
            ),
            child: const Icon(
              Icons.local_fire_department,
              color: Colors.white,
              size: 40,
            ),
          ),
          const SizedBox(width: 16),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  'Current Streak',
                  style: TextStyle(color: Colors.white70, fontSize: 14),
                ),
                Text(
                  '${stats.currentStreak} days',
                  style: const TextStyle(
                    color: Colors.white,
                    fontSize: 28,
                    fontWeight: FontWeight.bold,
                  ),
                ),
                const SizedBox(height: 4),
                const Text(
                  'Keep it up! 🔥',
                  style: TextStyle(color: Colors.white70, fontSize: 12),
                ),
              ],
            ),
          ),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
            decoration: BoxDecoration(
              color: Colors.white.withOpacity(0.2),
              borderRadius: BorderRadius.circular(20),
            ),
            child: const Row(
              children: [
                Icon(Icons.trending_up, color: Colors.white, size: 16),
                SizedBox(width: 4),
                Text(
                  'Active',
                  style: TextStyle(
                    color: Colors.white,
                    fontSize: 12,
                    fontWeight: FontWeight.bold,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildAchievementsSection() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            const Text(
              'Streak Achievements',
              style: TextStyle(
                fontSize: 20,
                fontWeight: FontWeight.bold,
                color: Colors.black87,
              ),
            ),
            const Spacer(),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
              decoration: BoxDecoration(
                color: Colors.orange.shade50,
                borderRadius: BorderRadius.circular(20),
                border: Border.all(color: Colors.orange.shade200),
              ),
              child: Text(
                'Current: ${stats.currentStreak} days',
                style: TextStyle(
                  color: Colors.orange.shade700,
                  fontWeight: FontWeight.bold,
                  fontSize: 12,
                ),
              ),
            ),
          ],
        ),
        const SizedBox(height: 12),
        GridView.count(
          shrinkWrap: true,
          physics: const NeverScrollableScrollPhysics(),
          crossAxisCount: 3,
          crossAxisSpacing: 12,
          mainAxisSpacing: 12,
          childAspectRatio: 0.85,
          children: [
            _buildStreakMedal(
              days: 7,
              title: '1 Week',
              description: '7 days',
              color: const Color(0xFFCD7F32), // Bronze
              icon: Icons.workspace_premium,
            ),
            _buildStreakMedal(
              days: 14,
              title: '2 Weeks',
              description: '14 days',
              color: const Color(0xFFC0C0C0), // Silver
              icon: Icons.workspace_premium,
            ),
            _buildStreakMedal(
              days: 30,
              title: '1 Month',
              description: '30 days',
              color: const Color(0xFFFFD700), // Gold
              icon: Icons.workspace_premium,
            ),
            _buildStreakMedal(
              days: 35,
              title: '5 Weeks',
              description: '35 days',
              color: Colors.blue,
              icon: Icons.emoji_events,
            ),
            _buildStreakMedal(
              days: 60,
              title: '2 Months',
              description: '60 days',
              color: Colors.purple,
              icon: Icons.emoji_events,
            ),
            _buildStreakMedal(
              days: 90,
              title: '3 Months',
              description: '90 days',
              color: Colors.indigo,
              icon: Icons.emoji_events,
            ),
            _buildStreakMedal(
              days: 100,
              title: '100 Days',
              description: 'Century',
              color: Colors.deepOrange,
              icon: Icons.stars,
            ),
            _buildStreakMedal(
              days: 180,
              title: '6 Months',
              description: '180 days',
              color: Colors.teal,
              icon: Icons.stars,
            ),
            _buildStreakMedal(
              days: 365,
              title: '1 Year',
              description: '365 days',
              color: Colors.amber,
              icon: Icons.stars,
            ),
          ],
        ),
      ],
    );
  }

  Widget _buildStreakMedal({
    required int days,
    required String title,
    required String description,
    required Color color,
    required IconData icon,
  }) {
    final bool unlocked = stats.currentStreak >= days;
    final bool isNextGoal =
        stats.currentStreak < days &&
        (stats.currentStreak >= days - 7 ||
            (days <= 7 && stats.currentStreak > 0));

    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: unlocked
            ? color.withOpacity(0.2)
            : isNextGoal
            ? Colors.grey.shade100
            : Colors.grey[200],
        borderRadius: BorderRadius.circular(12),
        border: Border.all(
          color: unlocked
              ? color
              : isNextGoal
              ? Colors.orange.shade300
              : Colors.grey[300]!,
          width: unlocked ? 3 : (isNextGoal ? 2 : 1),
        ),
        boxShadow: unlocked
            ? [
                BoxShadow(
                  color: color.withOpacity(0.3),
                  blurRadius: 8,
                  offset: const Offset(0, 4),
                ),
              ]
            : null,
      ),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Stack(
            alignment: Alignment.center,
            children: [
              if (unlocked)
                Icon(icon, color: color, size: 40)
              else
                Icon(icon, color: Colors.grey[400], size: 40),
              if (unlocked)
                Positioned(
                  top: 0,
                  right: 0,
                  child: Container(
                    padding: const EdgeInsets.all(2),
                    decoration: BoxDecoration(
                      color: color,
                      shape: BoxShape.circle,
                    ),
                    child: const Icon(
                      Icons.check,
                      color: Colors.white,
                      size: 12,
                    ),
                  ),
                ),
            ],
          ),
          const SizedBox(height: 8),
          Text(
            title,
            style: TextStyle(
              color: unlocked
                  ? (color is MaterialColor ? color.shade700 : color)
                  : Colors.grey[600],
              fontSize: 13,
              fontWeight: unlocked ? FontWeight.bold : FontWeight.normal,
            ),
            textAlign: TextAlign.center,
          ),
          const SizedBox(height: 2),
          Text(
            description,
            style: TextStyle(
              color: unlocked
                  ? (color is MaterialColor
                        ? color.shade600
                        : color.withOpacity(0.8))
                  : Colors.grey[500],
              fontSize: 10,
            ),
            textAlign: TextAlign.center,
          ),
          if (isNextGoal && !unlocked) ...[
            const SizedBox(height: 4),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
              decoration: BoxDecoration(
                color: Colors.orange.shade100,
                borderRadius: BorderRadius.circular(8),
              ),
              child: Text(
                '${days - stats.currentStreak} to go',
                style: TextStyle(
                  color: Colors.orange.shade700,
                  fontSize: 9,
                  fontWeight: FontWeight.bold,
                ),
              ),
            ),
          ],
        ],
      ),
    );
  }
}

class _HealthGameResult {
  final bool won;
  final String message;

  const _HealthGameResult({required this.won, required this.message});
}
