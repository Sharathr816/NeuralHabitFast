import 'package:flutter/material.dart';
import 'package:flutter_application_1/services/journal_service.dart';
import 'package:flutter_application_1/util/my_button.dart';
import 'package:speech_to_text/speech_to_text.dart' as stt;

class JournalPage extends StatefulWidget {
  final TextEditingController controller;
  final VoidCallback onCancel;
  final JournalService? service;

  const JournalPage({
    super.key,
    required this.controller,
    required this.onCancel,
    this.service,
  });

  @override
  State<JournalPage> createState() => _JournalPageState();
}

class _JournalPageState extends State<JournalPage> {
  String? selectedMood;
  late stt.SpeechToText _speech;
  bool _isListening = false;
  bool _isSaving = false;
  String? _statusMessage;
  late final JournalService _journalService;

  @override
  void initState() {
    super.initState();
    _speech = stt.SpeechToText();
    _journalService = widget.service ?? JournalService();
  }

  Future<void> _startListening() async {
    bool available = await _speech.initialize();
    if (available) {
      setState(() => _isListening = true);
      _speech.listen(
        onResult: (result) {
          setState(() {
            widget.controller.text = result.recognizedWords;
          });
        },
      );
    }
  }

  void _stopListening() {
    setState(() => _isListening = false);
    _speech.stop();
  }

  Future<void> _handleSave() async {
    final text = widget.controller.text.trim();
    if (text.isEmpty) {
      setState(() => _statusMessage = 'Please write something before saving.');
      return;
    }
    setState(() {
      _isSaving = true;
      _statusMessage = null;
    });
    try {
      // Submit journal with optional mobile data
      // Note: In a real app, you'd get these from device sensors/APIs
      final journalId = await _journalService.submitJournal(
        text: text,
        // Optional: Add mobile data if available
        // screenMinutes: 300,
        // unlockCount: 50,
        // sleepHours: 7.5,
        // steps: 8000,
        dominantEmotion: selectedMood?.toLowerCase(),
      );
      if (!mounted) return;
      widget.controller.clear();
      setState(() {
        selectedMood = null;
        _statusMessage = 'Journal saved successfully (ID: $journalId).';
      });
    } catch (err) {
      if (!mounted) return;
      setState(() {
        _statusMessage = err.toString();
      });
    } finally {
      if (mounted) {
        setState(() => _isSaving = false);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.grey[100],
      appBar: AppBar(
        title: const Text('Journal Entry'),
        backgroundColor: Colors.teal,
        foregroundColor: Colors.white,
        elevation: 2,
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 24),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              "How are you feeling today?",
              style: TextStyle(
                fontSize: 20,
                fontWeight: FontWeight.bold,
                color: Colors.black87,
              ),
            ),
            const SizedBox(height: 24),

            // Mood options with hover effect
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceEvenly,
              children: [
                _moodOption("Great", Icons.sentiment_very_satisfied, Colors.green),
                _moodOption("Good", Icons.sentiment_neutral, Colors.amber),
                _moodOption("Not Good", Icons.sentiment_dissatisfied, Colors.red),
              ],
            ),

            const SizedBox(height: 40),

            // Text Input Area with card style
            Container(
              decoration: BoxDecoration(
                color: Colors.white,
                borderRadius: BorderRadius.circular(16),
                boxShadow: const [
                  BoxShadow(
                    color: Colors.black12,
                    blurRadius: 6,
                    offset: Offset(0, 3),
                  ),
                ],
              ),
              padding: const EdgeInsets.all(16),
              child: TextField(
                controller: widget.controller,
                maxLines: 6,
                style: const TextStyle(fontSize: 16, color: Colors.black87),
                decoration: InputDecoration(
                  border: InputBorder.none,
                  hintText: "Write about your day...",
                  hintStyle: TextStyle(color: Colors.grey[400]),
                ),
              ),
            ),

            const SizedBox(height: 40),

            // Buttons row
            Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                _hoverableButton(
                  child: MyButton(
                    text: _isSaving ? "SAVING..." : "SAVE",
                    onPressed: _isSaving ? () {} : _handleSave,
                  ),
                ),
                const SizedBox(width: 24),
                _hoverableButton(
                  child: MyButton(
                    text: "CANCEL",
                    onPressed: () {
                      // Clear text controller
                      widget.controller.clear();
                      // Clear selected mood
                      setState(() {
                        selectedMood = null;
                      });
                      // Stop listening if active
                      if (_isListening) {
                        _stopListening();
                      }
                      // Call the onCancel callback if provided
                      widget.onCancel();
                    },
                  ),
                ),
              ],
            ),
            if (_statusMessage != null) ...[
              const SizedBox(height: 16),
              Text(
                _statusMessage!,
                style: TextStyle(
                  color: _statusMessage!.toLowerCase().contains('error')
                      ? Colors.red
                      : Colors.teal,
                ),
              ),
            ],
          ],
        ),
      ),

      // Floating mic button
      floatingActionButton: FloatingActionButton(
        backgroundColor: _isListening ? Colors.red : Colors.teal,
        onPressed: _isListening ? _stopListening : _startListening,
        child: Icon(
          _isListening ? Icons.stop : Icons.mic,
          color: Colors.white,
        ),
      ),
    );
  }

  Widget _hoverableButton({required Widget child}) {
    return MouseRegion(
      cursor: SystemMouseCursors.click,
      child: InkWell(
        borderRadius: BorderRadius.circular(8),
        onTap: () {},
        child: child,
      ),
    );
  }

  Widget _moodOption(String mood, IconData icon, Color color) {
    final bool isSelected = selectedMood == mood;

    return GestureDetector(
      onTap: () {
        setState(() {
          selectedMood = mood;
        });
      },
      child: MouseRegion(
        cursor: SystemMouseCursors.click,
        child: Column(
          children: [
            CircleAvatar(
              radius: 30,
              backgroundColor: isSelected
                  ? color.withValues(alpha: 0.2) // ✅ replaced withValues()
                  : Colors.grey[300],
              child: Icon(icon, size: 36, color: color),
            ),
            const SizedBox(height: 8),
            Text(
              mood,
              style: TextStyle(
                fontWeight: isSelected ? FontWeight.bold : FontWeight.normal,
                fontSize: 16,
                color: Colors.black87,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
