import 'package:flutter/material.dart';

class PatientMonitoringScreen extends StatelessWidget {
  const PatientMonitoringScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final activities = [
      {'name': 'Walking', 'confidence': '94%', 'room': 'Room 101'},
      {'name': 'Sitting', 'confidence': '88%', 'room': 'Room 102'},
      {'name': 'Limping', 'confidence': '76%', 'room': 'Room 104'},
      {'name': 'Sleeping', 'confidence': '97%', 'room': 'Room 103'},
    ];

    return Scaffold(
      appBar: AppBar(
        title: const Text('Patient Monitoring'),
      ),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.all(20),
          children: [
            Container(
              padding: const EdgeInsets.all(18),
              decoration: BoxDecoration(
                color: const Color(0xFFFFF3EF),
                borderRadius: BorderRadius.circular(18),
              ),
              child: Row(
                children: [
                  const Icon(
                    Icons.warning_amber_rounded,
                    color: Color(0xFFB95E52),
                    size: 32,
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: const [
                        Text(
                          'Fall detection event',
                          style: TextStyle(
                            fontWeight: FontWeight.w800,
                            color: Color(0xFF2E2A28),
                          ),
                        ),
                        SizedBox(height: 4),
                        Text(
                          'Room 104 • sudden downward movement detected',
                          style: TextStyle(color: Color(0xFF6E4B45)),
                        ),
                      ],
                    ),
                  ),
                  ElevatedButton(
                    onPressed: null,
                    child: const Text('Acknowledge'),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 20),
            const Text(
              'Live activity recognition',
              style: TextStyle(
                fontSize: 22,
                fontWeight: FontWeight.w800,
                color: Color(0xFF133230),
              ),
            ),
            const SizedBox(height: 12),
            GridView.count(
              shrinkWrap: true,
              physics: const NeverScrollableScrollPhysics(),
              crossAxisCount: 2,
              crossAxisSpacing: 12,
              mainAxisSpacing: 12,
              childAspectRatio: 1.15,
              children: activities.map((item) {
                final percentage = double.parse((item['confidence'] as String).replaceAll('%', '')) / 100;
                return Container(
                  padding: const EdgeInsets.all(14),
                  decoration: BoxDecoration(
                    color: Colors.white,
                    borderRadius: BorderRadius.circular(18),
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        item['name'] as String,
                        style: const TextStyle(
                          fontWeight: FontWeight.w700,
                          color: Color(0xFF143230),
                        ),
                      ),
                      const SizedBox(height: 6),
                      Text(
                        item['room'] as String,
                        style: const TextStyle(color: Color(0xFF627D7A)),
                      ),
                      const Spacer(),
                      Text(
                        item['confidence'] as String,
                        style: const TextStyle(
                          fontSize: 24,
                          fontWeight: FontWeight.w800,
                        ),
                      ),
                      const SizedBox(height: 8),
                      LinearProgressIndicator(
                        value: percentage,
                        minHeight: 8,
                        borderRadius: BorderRadius.circular(10),
                        backgroundColor: const Color(0xFFEAEFF0),
                        valueColor: const AlwaysStoppedAnimation<Color>(Color(0xFF1A7C6E)),
                      ),
                    ],
                  ),
                );
              }).toList(),
            ),
            const SizedBox(height: 20),
            Container(
              padding: const EdgeInsets.all(18),
              decoration: BoxDecoration(
                color: Colors.white,
                borderRadius: BorderRadius.circular(18),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: const [
                  Text(
                    'Mobility score',
                    style: TextStyle(
                      fontSize: 22,
                      fontWeight: FontWeight.w800,
                      color: Color(0xFF133230),
                    ),
                  ),
                  SizedBox(height: 12),
                  Text('78 / 100', style: TextStyle(fontSize: 32, fontWeight: FontWeight.w800)),
                  SizedBox(height: 8),
                  LinearProgressIndicator(
                    value: 0.78,
                    minHeight: 10,
                    backgroundColor: Color(0xFFE7EFEE),
                    valueColor: AlwaysStoppedAnimation<Color>(Color(0xFF1A7C6E)),
                  ),
                  SizedBox(height: 12),
                  Text('Walking stability: 86%'),
                  Text('Active time today: 42 min'),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}
