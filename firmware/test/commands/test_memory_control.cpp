#include <gtest/gtest.h>
#include "scrutiny.h"
#include "scrutiny_test.h"

class TestMemoryControl : public ScrutinyTest
{
protected:
   scrutiny::Timebase tb;
   scrutiny::MainHandler scrutiny_handler;
   scrutiny::config config

   virtual void SetUp() 
   {
      scrutiny::Config config;
      scrutiny_handler.init(&config);
      scrutiny_handler.comm()->connect();
   }
};

TEST_F(TestMemoryControl, TestReadSingleAddress) 
{

}
