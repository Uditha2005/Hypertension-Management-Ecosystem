import 'package:flutter/material.dart';

import 'medicine_verification_screen.dart';
import 'mental_wellness_screen.dart';
import 'nutritional_intelligence_screen.dart';
import 'patient_monitoring_screen.dart';

class HomeScreen extends StatelessWidget {
  const HomeScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final items = [
      {
        'title': 'Medicine Verification',
        'subtitle': 'Scan labels, compare dosage, and flag risk.',
        'accent': const Color(0xFF1A7C6E),
        'icon': Icons.medication_rounded,
        'screen': const MedicineVerificationScreen(),
      },
      {
        'title': 'Mental Wellness',
        'subtitle': 'Track stress, mood, and attention patterns.',
        'accent': const Color(0xFF4E7AC4),
        'icon': Icons.psychology_alt_rounded,
        'screen': const MentalWellnessScreen(),
      },
      {
        'title': 'Nutritional Intelligence',
        'subtitle': 'Review meals and smarter blood-pressure choices.',
        'accent': const Color(0xFF3A8C5A),
        'icon': Icons.restaurant_menu_rounded,
        'screen': const NutritionalIntelligenceScreen(),
      },
      {
        'title': 'Patient Monitoring',
        'subtitle': 'Monitor movement, mobility, and live safety alerts.',
        'accent': const Color(0xFFB85E52),
        'icon': Icons.monitor_heart_rounded,
        'screen': const PatientMonitoringScreen(),
      },
    ];

    return Scaffold(
      appBar: AppBar(
        title: const Text('Hypertension Care'),
        centerTitle: true,
      ),
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.fromLTRB(20, 14, 20, 20),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text(
                'Good morning, Maya',
                style: TextStyle(
                  fontSize: 28,
                  fontWeight: FontWeight.w800,
                  color: Color(0xFF12342F),
                ),
              ),
              const SizedBox(height: 8),
              const Text(
                'Your care dashboard is ready for review.',
                style: TextStyle(
                  fontSize: 15,
                  color: Color(0xFF617774),
                ),
              ),
              const SizedBox(height: 18),
              Container(
                width: double.infinity,
                padding: const EdgeInsets.all(18),
                decoration: BoxDecoration(
                  gradient: const LinearGradient(
                    colors: [Color(0xFF1A7C6E), Color(0xFF0E5C54)],
                    begin: Alignment.topLeft,
                    end: Alignment.bottomRight,
                  ),
                  borderRadius: BorderRadius.circular(22),
                ),
                child: Row(
                  children: [
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: const [
                          Text(
                            'Care score',
                            style: TextStyle(
                              color: Colors.white70,
                              fontSize: 13,
                            ),
                          ),
                          SizedBox(height: 8),
                          Text(
                            '84%',
                            style: TextStyle(
                              color: Colors.white,
                              fontSize: 34,
                              fontWeight: FontWeight.w800,
                            ),
                          ),
                        ],
                      ),
                    ),
                    Container(
                      padding: const EdgeInsets.all(12),
                      decoration: BoxDecoration(
                        color: Colors.white.withOpacity(0.14),
                        borderRadius: BorderRadius.circular(14),
                      ),
                      const Icon(
                        Icons.favorite_rounded,
                        color: Colors.white,
                        size: 32,
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 22),
              Expanded(
                child: GridView.builder(
                  itemCount: items.length,
                  gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
                    crossAxisCount: 2,
                    crossAxisSpacing: 16,
                    mainAxisSpacing: 16,
                    childAspectRatio: 0.95,
                  ),
                  itemBuilder: (context, index) {
                    final item = items[index];
                    return GestureDetector(
                      onTap: () {
                        Navigator.push(
                          context,
                          MaterialPageRoute(
                            builder: (_) => item['screen'] as Widget,
                          ),
                        );
                      },
                      child: Container(
                        padding: const EdgeInsets.all(16),
                        decoration: BoxDecoration(
                          color: Colors.white,
                          borderRadius: BorderRadius.circular(22),
                          boxShadow: [
                            BoxShadow(
                              color: Colors.black.withOpacity(0.05),
                              blurRadius: 12,
                              offset: const Offset(0, 6),
                            ),
                          ],
                        ),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Container(
                              width: 52,
                              height: 52,
                              decoration: BoxDecoration(
                                color: (item['accent'] as Color).withOpacity(0.12),
                                borderRadius: BorderRadius.circular(16),
                              ),
                              child: Icon(
                                item['icon'] as IconData,
                                color: item['accent'] as Color,
                                size: 28,
                              ),
                            ),
                            const SizedBox(height: 18),
                            Text(
                              item['title'] as String,
                              style: const TextStyle(
                                fontSize: 17,
                                fontWeight: FontWeight.w800,
                                color: Color(0xFF17352E),
                              ),
                            ),
                            const SizedBox(height: 10),
                            Text(
                              item['subtitle'] as String,
                              style: const TextStyle(
                                fontSize: 12.5,
                                height: 1.5,
                                color: Color(0xFF647B78),
                              ),
                            ),
                            const Spacer(),
                            Row(
                              children: [
                                const Spacer(),
                                Icon(
                                  Icons.arrow_forward_rounded,
                                  color: item['accent'] as Color,
                                ),
                              ],
                            ),
                          ],
                        ),
                      ),
                    );
                  },
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
