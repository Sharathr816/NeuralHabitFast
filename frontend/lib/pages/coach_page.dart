// import 'package:flutter/material.dart';
// import '../services/coach_service.dart';
// import '../state/user_session.dart';

// class CoachPage extends StatefulWidget {
//   const CoachPage({super.key});

//   @override
//   State<CoachPage> createState() => _CoachPageState();
// }

// class _CoachPageState extends State<CoachPage> {
//   final CoachService _coachService = CoachService();
//   final UserSession _session = UserSession();
//   bool _isLoading = false;
//   Map<String, dynamic>? _coaching;
//   String? _error;

//   @override
//   void initState() {
//     super.initState();
//     _loadCoaching();
//   }

//   Future<void> _loadCoaching() async {
//     setState(() {
//       _isLoading = true;
//       _error = null;
//     });

//     try {
//       final coaching = await _coachService.getCoaching();
//       setState(() {
//         _coaching = coaching;
//         _isLoading = false;
//       });
//     } catch (e) {
//       setState(() {
//         _error = e.toString();
//         _isLoading = false;
//       });
//     }
//   }

//   @override
//   Widget build(BuildContext context) {
//     return Scaffold(
//       backgroundColor: Colors.grey[100],
//       appBar: AppBar(
//         title: const Text('Habit Coach'),
//         backgroundColor: Colors.teal,
//         foregroundColor: Colors.white,
//         elevation: 2,
//         actions: [
//           IconButton(
//             icon: const Icon(Icons.refresh),
//             onPressed: _isLoading ? null : _loadCoaching,
//             tooltip: 'Refresh coaching',
//           ),
//         ],
//       ),
//       body: _isLoading
//           ? const Center(child: CircularProgressIndicator())
//           : _error != null
//               ? _buildErrorView()
//               : _coaching != null
//                   ? _buildCoachingView()
//                   : _buildEmptyView(),
//     );
//   }

//   Widget _buildErrorView() {
//     return Center(
//       child: Padding(
//         padding: const EdgeInsets.all(24.0),
//         child: Column(
//           mainAxisAlignment: MainAxisAlignment.center,
//           children: [
//             Icon(Icons.error_outline, size: 64, color: Colors.red[300]),
//             const SizedBox(height: 16),
//             Text(
//               'Error',
//               style: Theme.of(context).textTheme.headlineSmall,
//             ),
//             const SizedBox(height: 8),
//             Text(
//               _error ?? 'Unknown error',
//               textAlign: TextAlign.center,
//               style: TextStyle(color: Colors.grey[700]),
//             ),
//             const SizedBox(height: 24),
//             ElevatedButton(
//               onPressed: _loadCoaching,
//               child: const Text('Try Again'),
//             ),
//           ],
//         ),
//       ),
//     );
//   }

//   Widget _buildEmptyView() {
//     return Center(
//       child: Padding(
//         padding: const EdgeInsets.all(24.0),
//         child: Column(
//           mainAxisAlignment: MainAxisAlignment.center,
//           children: [
//             Icon(Icons.psychology_outlined, size: 64, color: Colors.teal[300]),
//             const SizedBox(height: 16),
//             Text(
//               'No Coaching Available',
//               style: Theme.of(context).textTheme.headlineSmall,
//             ),
//             const SizedBox(height: 8),
//             Text(
//               'Please submit a journal entry first to get personalized coaching.',
//               textAlign: TextAlign.center,
//               style: TextStyle(color: Colors.grey[700]),
//             ),
//           ],
//         ),
//       ),
//     );
//   }

//   Widget _buildCoachingView() {
//     final reply = _coaching!['reply'] as String? ?? '';
//     final microHabits = _coaching!['micro_habits'] as List<dynamic>? ?? [];
//     final evidence = _coaching!['evidence'] as List<dynamic>? ?? [];
//     final analysisSnapshot = _coaching!['analysis_snapshot'] as Map<String, dynamic>? ?? {};

//     return SingleChildScrollView(
//       padding: const EdgeInsets.all(16),
//       child: Column(
//         crossAxisAlignment: CrossAxisAlignment.start,
//         children: [
//           // Coach Reply Card
//           Card(
//             elevation: 2,
//             shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
//             child: Padding(
//               padding: const EdgeInsets.all(16),
//               child: Column(
//                 crossAxisAlignment: CrossAxisAlignment.start,
//                 children: [
//                   Row(
//                     children: [
//                       Icon(Icons.psychology, color: Colors.teal[700]),
//                       const SizedBox(width: 8),
//                       Text(
//                         'Your Coach',
//                         style: Theme.of(context).textTheme.titleMedium?.copyWith(
//                               fontWeight: FontWeight.bold,
//                               color: Colors.teal[700],
//                             ),
//                       ),
//                     ],
//                   ),
//                   const SizedBox(height: 12),
//                   Text(
//                     reply,
//                     style: const TextStyle(fontSize: 15, height: 1.5),
//                   ),
//                 ],
//               ),
//             ),
//           ),

//           const SizedBox(height: 16),

//           // Micro Habits
//           if (microHabits.isNotEmpty) ...[
//             Text(
//               'Recommended Micro-Habits',
//               style: Theme.of(context).textTheme.titleLarge?.copyWith(
//                     fontWeight: FontWeight.bold,
//                   ),
//             ),
//             const SizedBox(height: 12),
//             ...microHabits.map((habit) => _buildHabitCard(habit)),
//           ],

//           const SizedBox(height: 16),

//           // Analysis Snapshot
//           if (analysisSnapshot.isNotEmpty) ...[
//             Text(
//               'Analysis Summary',
//               style: Theme.of(context).textTheme.titleLarge?.copyWith(
//                     fontWeight: FontWeight.bold,
//                   ),
//             ),
//             const SizedBox(height: 12),
//             Card(
//               elevation: 1,
//               shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
//               child: Padding(
//                 padding: const EdgeInsets.all(16),
//                 child: Column(
//                   crossAxisAlignment: CrossAxisAlignment.start,
//                   children: [
//                     _buildAnalysisRow('Risk Score', analysisSnapshot['risk_score']?.toString() ?? 'N/A'),
//                     if (analysisSnapshot['dominant_emotion'] != null)
//                       _buildAnalysisRow('Dominant Emotion', analysisSnapshot['dominant_emotion']),
//                     if (analysisSnapshot['top_features'] != null)
//                       ...(analysisSnapshot['top_features'] as List<dynamic>?)
//                               ?.map((feat) => _buildAnalysisRow(
//                                     feat['feature']?.toString() ?? 'Feature',
//                                     'Impact: ${feat['shap']?.toStringAsFixed(3) ?? "N/A"}',
//                                   )) ??
//                           [],
//                   ],
//                 ),
//               ),
//             ),
//           ],
//         ],
//       ),
//     );
//   }

//   Widget _buildHabitCard(Map<String, dynamic> habit) {
//     return Card(
//       elevation: 2,
//       margin: const EdgeInsets.only(bottom: 12),
//       shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
//       child: Padding(
//         padding: const EdgeInsets.all(16),
//         child: Column(
//           crossAxisAlignment: CrossAxisAlignment.start,
//           children: [
//             Row(
//               children: [
//                 Icon(Icons.check_circle_outline, color: Colors.teal[700]),
//                 const SizedBox(width: 8),
//                 Expanded(
//                   child: Text(
//                     habit['title']?.toString() ?? 'Habit',
//                     style: Theme.of(context).textTheme.titleMedium?.copyWith(
//                           fontWeight: FontWeight.bold,
//                         ),
//                   ),
//                 ),
//               ],
//             ),
//             const SizedBox(height: 8),
//             if (habit['why'] != null)
//               Padding(
//                 padding: const EdgeInsets.only(bottom: 8),
//                 child: Text(
//                   habit['why'].toString(),
//                   style: TextStyle(color: Colors.grey[700], fontSize: 13),
//                 ),
//               ),
//             if (habit['plan'] != null)
//               Padding(
//                 padding: const EdgeInsets.only(bottom: 8),
//                 child: Row(
//                   children: [
//                     Icon(Icons.schedule, size: 16, color: Colors.teal[700]),
//                     const SizedBox(width: 4),
//                     Expanded(
//                       child: Text(
//                         habit['plan'].toString(),
//                         style: const TextStyle(fontSize: 13),
//                       ),
//                     ),
//                   ],
//                 ),
//               ),
//             if (habit['duration_minutes'] != null)
//               Padding(
//                 padding: const EdgeInsets.only(bottom: 8),
//                 child: Row(
//                   children: [
//                     Icon(Icons.timer, size: 16, color: Colors.teal[700]),
//                     const SizedBox(width: 4),
//                     Text(
//                       '${habit['duration_minutes']} minutes',
//                       style: const TextStyle(fontSize: 13),
//                     ),
//                   ],
//                 ),
//               ),
//             if (habit['metric'] != null)
//               Container(
//                 padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
//                 decoration: BoxDecoration(
//                   color: Colors.teal[50],
//                   borderRadius: BorderRadius.circular(8),
//                 ),
//                 child: Row(
//                   mainAxisSize: MainAxisSize.min,
//                   children: [
//                     Icon(Icons.track_changes, size: 14, color: Colors.teal[700]),
//                     const SizedBox(width: 4),
//                     Text(
//                       'Metric: ${habit['metric']}',
//                       style: TextStyle(
//                         fontSize: 12,
//                         color: Colors.teal[700],
//                         fontWeight: FontWeight.w500,
//                       ),
//                     ),
//                   ],
//                 ),
//               ),
//           ],
//         ),
//       ),
//     );
//   }

//   Widget _buildAnalysisRow(String label, String value) {
//     return Padding(
//       padding: const EdgeInsets.only(bottom: 8),
//       child: Row(
//         crossAxisAlignment: CrossAxisAlignment.start,
//         children: [
//           SizedBox(
//             width: 120,
//             child: Text(
//               label,
//               style: const TextStyle(fontWeight: FontWeight.w500),
//             ),
//           ),
//           Expanded(child: Text(value)),
//         ],
//       ),
//     );
//   }
// }


