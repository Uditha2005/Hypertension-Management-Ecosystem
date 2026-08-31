import 'package:flutter/material.dart';

class MentalWellnessScreen extends StatelessWidget {
  const MentalWellnessScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final metrics = [
      {'label': 'Heart Rate', 'value': '72', 'unit': 'BPM', 'color': const Color(0xFFDE6A55)},
      {'label': 'Temperature', 'value': '36.7', 'unit': '°C', 'color': const Color(0xFFCF9A2B)},
      {'label': 'Stress', 'value': 'Low', 'unit': 'State', 'color': const Color(0xFF1F7A6B)},
      {'label': 'Emotion', 'value': 'Focused', 'unit': 'Live', 'color': const Color(0xFF4A7AA6)},
    ];

    return Scaffold(
      appBar: AppBar(
        title: const Text('Mental Wellness'),
      ),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.all(20),
          children: [
            const Text(
              'Emotional and cognitive support',
              style: TextStyle(
                fontSize: 28,
                fontWeight: FontWeight.w800,
                color: Color(0xFF15342F),
              ),
            ),
            const SizedBox(height: 8),
            const Text(
              'A calm view of stress, focus, and emotional readiness.',
              style: TextStyle(
                color: Color(0xFF657B77),
                fontSize: 15,
              ),
            ),
            const SizedBox(height: 18),
            GridView.count(
              shrinkWrap: true,
              physics: const NeverScrollableScrollPhysics(),
              crossAxisCount: 2,
              crossAxisSpacing: 14,
              mainAxisSpacing: 14,
              childAspectRatio: 1.1,
              children: metrics.map((metric) {
                final color = metric['color'] as Color;
                return Container(
                  padding: const EdgeInsets.all(16),
                  decoration: BoxDecoration(
                    color: Colors.white,
                    borderRadius: BorderRadius.circular(18),
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Container(
                        width: 42,
                        height: 42,
                        decoration: BoxDecoration(
                          color: color.withOpacity(0.14),
                          borderRadius: BorderRadius.circular(12),
                        ),
                        child: Icon(Icons.favorite_rounded, color: color),
                      ),
                      const SizedBox(height: 12),
                      Text(
                        metric['label'] as String,
                        style: const TextStyle(
                          fontSize: 12,
                          color: Color(0xFF667E7A),
                        ),
                      ),
                      const SizedBox(height: 6),
                      Row(
                        crossAxisAlignment: CrossAxisAlignment.end,
                        children: [
                          Text(
                            metric['value'] as String,
                            style: const TextStyle(
                              fontSize: 26,
                              fontWeight: FontWeight.w800,
                              color: Color(0xFF143230),
                            ),
                          ),
                          const SizedBox(width: 6),
                          Text(
                            metric['unit'] as String,
                            style: const TextStyle(
                              fontSize: 12,
                              color: Color(0xFF667E7A),
                            ),
                          ),
                        ],
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
                children: [
                  const Text(
                    'Recommended support',
                    style: TextStyle(
                      fontSize: 20,
                      fontWeight: FontWeight.w800,
                      color: Color(0xFF12342F),
                    ),
                  ),
                  const SizedBox(height: 10),
                  const Text(
                    'Stress remains low and focus is stable. A brief breathing routine may help maintain calm and reduce strain.',
                    style: TextStyle(
                      color: Color(0xFF627D7A),
                      height: 1.5,
                    ),
                  ),
                  const SizedBox(height: 16),
                  ElevatedButton.icon(
                    onPressed: null,
                    icon: const Icon(Icons.self_improvement_rounded),
                    label: const Text('Start breathing guide'),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}
