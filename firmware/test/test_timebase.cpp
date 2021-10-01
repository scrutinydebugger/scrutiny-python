#include <gtest/gtest.h>
#include "scrutiny.h"


TEST(TestTimebase, CheckTimeouts) 
{
   scrutiny::Timebase tb;
   uint32_t timestamp;

   timestamp = tb.get_timestamp();
   tb.step(100);
   EXPECT_TRUE(tb.is_elapsed(timestamp, 99));
   EXPECT_TRUE(tb.is_elapsed(timestamp, 100));
   EXPECT_FALSE(tb.is_elapsed(timestamp, 101));

   timestamp = tb.get_timestamp();
   tb.step(100);
   EXPECT_TRUE(tb.is_elapsed(timestamp, 99));
   EXPECT_TRUE(tb.is_elapsed(timestamp, 100));
   EXPECT_FALSE(tb.is_elapsed(timestamp, 101));

   tb.reset();
   timestamp = tb.get_timestamp();
   EXPECT_EQ(timestamp, 0u);

   tb.step(0x7FFFFFFF);
   EXPECT_TRUE(tb.is_elapsed(timestamp, 0x7FFFFFFE));
   EXPECT_TRUE(tb.is_elapsed(timestamp, 0x7FFFFFFF));
   EXPECT_FALSE(tb.is_elapsed(timestamp, 0x80000000));

   tb.reset();
   tb.step(0xFFFFFFFF);
   timestamp = tb.get_timestamp();
   tb.step(2);
   EXPECT_TRUE(tb.is_elapsed(timestamp, 1));
   EXPECT_TRUE(tb.is_elapsed(timestamp, 2));
   EXPECT_FALSE(tb.is_elapsed(timestamp, 3));

}

