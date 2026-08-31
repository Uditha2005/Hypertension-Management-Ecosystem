import 'package:flutter/material.dart';

class NutritionalIntelligenceScreen extends StatelessWidget {
  const NutritionalIntelligenceScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final foods = [
      {'name': 'Grilled chicken', 'portion': '120 g'},
      {'name': 'Steamed rice', 'portion': '180 g'},
      {'name': 'Garden salad', 'portion': '95 g'},
    ];

    return Scaffold(
      appBar: AppBar(
        title: const Text('Nutritional Intelligence'),
      ),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.all(20),
          children: [
            const Text(
              'What is on your plate?',
              style: TextStyle(
                fontSize: 28,
                fontWeight: FontWeight.w800,
                color: Color(0xFF14342F),
              ),
            ),
            const SizedBox(height: 8),
            const Text(
              'Upload a meal photo to estimate calories and nutrient balance.',
              style: TextStyle(
                color: Color(0xFF647B78),
                fontSize: 15,
              ),
            ),
            const SizedBox(height: 18),
            Container(
              padding: const EdgeInsets.all(18),
              decoration: BoxDecoration(
                color: Colors.white,
                borderRadius: BorderRadius.circular(20),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text(
                    'Meal scan',
                    style: TextStyle(
                      fontSize: 20,
                      fontWeight: FontWeight.w800,
                      color: Color(0xFF14342F),
                    ),
                  ),
                  const SizedBox(height: 12),
                  Container(
                    height: 180,
                    width: double.infinity,
                    decoration: BoxDecoration(
                      color: const Color(0xFFEAF5EE),
                      borderRadius: BorderRadius.circular(18),
                      border: Border.all(color: const Color(0xFF7AB79A)),
                    ),
                    child: const Center(
                      child: Icon(
                        Icons.add_photo_alternate_outlined,
                        size: 54,
                        color: Color(0xFF2E7D4A),
                      ),
                    ),
                  ),
                  const SizedBox(height: 16),
                  Row(
                    children: [
                      Expanded(
                        child: ElevatedButton.icon(
                          onPressed: null,
                          icon: const Icon(Icons.upload_file_rounded),
                          label: const Text('Upload'),
                        ),
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: OutlinedButton.icon(
                          onPressed: null,
                          icon: const Icon(Icons.analytics_rounded),
                          label: const Text('Analyze'),
                        ),
                      ),
                    ],
                  ),
                ],
              ),
            ),
            const SizedBox(height: 22),
            const Text(
              'Detected items',
              style: TextStyle(
                fontSize: 20,
                fontWeight: FontWeight.w800,
                color: Color(0xFF14342F),
              ),
            ),
            const SizedBox(height: 10),
            ...foods.map(
              (item) => Container(
                margin: const EdgeInsets.only(bottom: 10),
                padding: const EdgeInsets.all(14),
                decoration: BoxDecoration(
                  color: Colors.white,
                  borderRadius: BorderRadius.circular(16),
                ),
                child: Row(
                  children: [
                    const Icon(
                      Icons.restaurant_menu_rounded,
                      color: Color(0xFF2E7D4A),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Text(item['name'] as String),
                    ),
                    Text(
                      item['portion'] as String,
                      style: const TextStyle(
                        fontWeight: FontWeight.w700,
                        color: Color(0xFF2E7D4A),
                      ),
                    ),
                  ],
                ),
              ),
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
                    'Nutrition summary',
                    style: TextStyle(
                      fontSize: 20,
                      fontWeight: FontWeight.w800,
                      color: Color(0xFF14342F),
                    ),
                  ),
                  SizedBox(height: 12),
                  Text('520 kcal', style: TextStyle(fontSize: 28, fontWeight: FontWeight.w800)),
                  SizedBox(height: 8),
                  Text('Protein: 28 g'),
                  Text('Carbs: 48 g'),
                  Text('Fats: 18 g'),
                  Text('Sodium: 610 mg'),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}
