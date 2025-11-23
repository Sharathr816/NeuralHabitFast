// import 'package:flutter/material.dart';
// import 'pages/gamificationpage.dart';
// import 'pages/homepage.dart';
// import 'pages/ai_assistant.dart';
// import 'pages/first_page.dart';
// import 'pages/journal.dart';
// import 'pages/settings_page.dart';

// // import 'util/mobile_data.dart';
// // import 'pages/mobile_stats_debug.dart';
// void main() {
//   WidgetsFlutterBinding.ensureInitialized();
//   runApp(MyApp());
// }

// class MyApp extends StatelessWidget {
//   final _controller = TextEditingController();
//   MyApp({super.key});
//   void saveNewTask() {}
//   @override
//   Widget build(BuildContext context) {
//     return MaterialApp(
//       debugShowCheckedModeBanner: false,
//       home: FirstPage(),
//       routes: {
//         '/firstpage': (context) => FirstPage(),
//         '/homepage': (context) => HomePage(),
//         '/settingspage': (context) => SettingsPage(),
//         '/aiassistantpage': (context) => AiAssistant(),
//         '/journalpage': (context) => JournalPage(
//           controller: _controller,
//           onSave: saveNewTask,
//           onCancel: () {
//             _controller.clear(); // ✅ just clear the text
//           },
//         ),
//         '/gamificationpage': (context) => GamificationPage(),
//         //'/debug_mobile': (context) => const MobileDebugPage(),
//       },
//     );
//   }
// }


import 'package:flutter/material.dart';
import 'package:flutter_application_1/pages/auth_page.dart';
import 'package:flutter_application_1/pages/first_page.dart';
import 'package:flutter_application_1/pages/gamificationpage.dart';
import 'package:flutter_application_1/pages/homepage.dart';
import 'package:flutter_application_1/pages/ai_assistant.dart';
// import 'package:flutter_application_1/pages/coach_page.dart';
import 'package:flutter_application_1/pages/journal.dart';
import 'package:flutter_application_1/pages/settings_page.dart';
import 'package:flutter_application_1/services/auth_service.dart';
import 'package:flutter_application_1/state/user_session.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await AuthService().hydrate();
  runApp(const NeuralHabitApp());
}

class NeuralHabitApp extends StatelessWidget {
  const NeuralHabitApp({super.key});

  @override
  Widget build(BuildContext context) {
    final session = UserSession();

    return AnimatedBuilder(
      animation: session,
      builder: (context, _) {
        final isLoggedIn = session.isAuthenticated;

        return MaterialApp(
          debugShowCheckedModeBanner: false,
          title: 'NeuralHabit',
          theme: ThemeData(
            colorSchemeSeed: Colors.teal,
            useMaterial3: true,
          ),
          home: isLoggedIn ? const FirstPage() : const AuthPage(),
          routes: {
            '/firstpage': (context) => const FirstPage(),
            '/homepage': (context) => const HomePage(),
            '/settingspage': (context) => const SettingsPage(),
            '/aiassistantpage': (context) => const AiAssistant(),
            // '/coachpage': (context) => const CoachPage(),
            '/journalpage': (context) => JournalPage(
                  controller: TextEditingController(),
                  onCancel: () {},
                ),
            '/gamificationpage': (context) => const GamificationPage(),
            '/auth': (context) => const AuthPage(),
          },
        );
      },
    );
  }
}
