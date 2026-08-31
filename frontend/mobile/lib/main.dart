import 'package:flutter/material.dart';

import 'screens/home_screen.dart';

void main() {
  runApp(const HypertensionEcosystemApp());
}

class HypertensionEcosystemApp extends StatelessWidget {
  const HypertensionEcosystemApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Hypertension Ecosystem',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(
          seedColor: const Color(0xFF1B7A6B),
          brightness: Brightness.light,
        ),
        scaffoldBackgroundColor: const Color(0xFFF5F8F7),
        appBarTheme: const AppBarTheme(
          backgroundColor: Colors.white,
          foregroundColor: Color(0xFF19362F),
          elevation: 0,
        ),
        cardTheme: CardThemeData(
          elevation: 0,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(18),
          ),
          margin: EdgeInsets.zero,
        ),
        useMaterial3: true,
      ),
      home: const HomeScreen(),
    );
  }
}
